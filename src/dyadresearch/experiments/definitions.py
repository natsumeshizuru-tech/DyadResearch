from __future__ import annotations

import ast
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

DefinitionKind = Literal["strategy", "factor"]
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
STRATEGY_TYPES = {"buy_and_hold", "moving_average_cross", "low_volume_ratio_momentum"}
BAR_FIELDS = {"open", "high", "low", "close", "volume", "amount"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS research_definitions (
    kind TEXT NOT NULL CHECK(kind IN ('strategy', 'factor')),
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    code TEXT NOT NULL,
    implementation TEXT NOT NULL,
    config_json TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    is_builtin INTEGER NOT NULL DEFAULT 0 CHECK(is_builtin IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY(kind, name)
);
CREATE INDEX IF NOT EXISTS idx_research_definitions_kind_updated
    ON research_definitions(kind, updated_at DESC);
"""

MOVING_AVERAGE_CODE = """STRATEGY = {
    "type": "moving_average_cross",
    "title": "双均线择时",
    "description": "短均线上穿买入、下穿卖出; 下一 bar 成交并遵守 T+1。",
    "parameters": {"fast": 5, "slow": 20, "quantity": 1000},
}
"""

LEGACY_BUY_AND_HOLD_CODE = """STRATEGY = {
    "type": "buy_and_hold",
    "title": "买入并持有",
    "description": "首个可交易信号后买入并持有。",
    "parameters": {"quantity": 1000},
}
"""

BUY_AND_HOLD_CODE = """STRATEGY = {
    "type": "buy_and_hold",
    "title": "买入并持有",
    "description": "下一可交易 bar 开盘按整手尽可能满仓买入; 并持有到回测结束。",
    "parameters": {"allocation_ratio": 1.0},
}
"""

LOW_VOLUME_RATIO_CODE = """STRATEGY = {
    "type": "low_volume_ratio_momentum",
    "title": "低量比动量策略",
    "description": (
        "沪深主板、市值小于300亿元; 涨幅超过7%且5日实时量比低于0.6时触发, "
        "下一分钟开盘未涨停则买入20%总仓位, 最多持有5只, 次日开盘全仓卖出。"
    ),
    "parameters": {
        "market_cap_max": 30000000000,
        "rise_threshold": 0.07,
        "volume_ratio_max": 0.60,
        "volume_lookback_days": 5,
        "allocation_ratio": 0.20,
        "max_positions": 5,
    },
}
"""

MOMENTUM_FACTOR_CODE = """FACTOR = {
    "title": "20周期动量",
    "description": "20-bar close-to-close momentum",
    "expression": "close[-1] / close[0] - 1",
    "input_fields": ["close"],
    "lookback": 20,
    "frequency": "1d",
    "higher_is_better": True,
}
"""

VOLATILITY_FACTOR_CODE = """FACTOR = {
    "title": "20周期波动率",
    "description": "20-bar population volatility of simple returns",
    "expression": "pstdev(returns(close))",
    "input_fields": ["close"],
    "lookback": 20,
    "frequency": "1d",
    "higher_is_better": False,
}
"""

TURNOVER_FACTOR_CODE = """FACTOR = {
    "title": "20周期平均成交额",
    "description": "20-bar average traded amount",
    "expression": "mean(amount)",
    "input_fields": ["amount"],
    "lookback": 20,
    "frequency": "1d",
    "higher_is_better": True,
}
"""


@dataclass(frozen=True, slots=True)
class ResearchDefinition:
    kind: DefinitionKind
    name: str
    title: str
    description: str
    code: str
    implementation: str
    config: dict[str, Any]
    version: int
    is_builtin: bool
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "code": self.code,
            "implementation": self.implementation,
            "config": self.config,
            "version": self.version,
            "is_builtin": self.is_builtin,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DefinitionStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.executescript(SCHEMA)
            for kind, name, code in _builtin_definitions():
                parsed = parse_definition_code(kind, code)
                connection.execute(
                    "INSERT OR IGNORE INTO research_definitions("
                    "kind, name, title, description, code, implementation, config_json, "
                    "is_builtin) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                    (
                        kind,
                        name,
                        parsed["title"],
                        parsed["description"],
                        code,
                        parsed["implementation"],
                        _json(parsed["config"]),
                    ),
                )
            buy_and_hold = parse_definition_code("strategy", BUY_AND_HOLD_CODE)
            connection.execute(
                "UPDATE research_definitions SET title=?, description=?, code=?, "
                "implementation=?, config_json=?, version=version+1, "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
                "WHERE kind='strategy' AND name='buy_and_hold' AND is_builtin=1 "
                "AND version=1 AND code=?",
                (
                    buy_and_hold["title"],
                    buy_and_hold["description"],
                    BUY_AND_HOLD_CODE,
                    buy_and_hold["implementation"],
                    _json(buy_and_hold["config"]),
                    LEGACY_BUY_AND_HOLD_CODE,
                ),
            )

    def list(self, kind: DefinitionKind) -> tuple[ResearchDefinition, ...]:
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                "SELECT kind, name, title, description, code, implementation, config_json, "
                "version, is_builtin, created_at, updated_at FROM research_definitions "
                "WHERE kind=? ORDER BY is_builtin DESC, name",
                (kind,),
            ).fetchall()
        return tuple(_record(row) for row in rows)

    def get(self, kind: DefinitionKind, name: str) -> ResearchDefinition:
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT kind, name, title, description, code, implementation, config_json, "
                "version, is_builtin, created_at, updated_at FROM research_definitions "
                "WHERE kind=? AND name=?",
                (kind, name),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown {kind}: {name}")
        return _record(row)

    def create(self, kind: DefinitionKind, name: str, code: str) -> ResearchDefinition:
        normalized = validate_definition_name(name)
        parsed = parse_definition_code(kind, code)
        self.initialize()
        try:
            with sqlite3.connect(self.path) as connection:
                connection.execute(
                    "INSERT INTO research_definitions("
                    "kind, name, title, description, code, implementation, config_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        kind,
                        normalized,
                        parsed["title"],
                        parsed["description"],
                        code,
                        parsed["implementation"],
                        _json(parsed["config"]),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"{kind} already exists: {normalized}") from exc
        return self.get(kind, normalized)

    def update(self, kind: DefinitionKind, name: str, code: str) -> ResearchDefinition:
        parsed = parse_definition_code(kind, code)
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            cursor = connection.execute(
                "UPDATE research_definitions SET title=?, description=?, code=?, "
                "implementation=?, config_json=?, version=version+1, "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
                "WHERE kind=? AND name=?",
                (
                    parsed["title"],
                    parsed["description"],
                    code,
                    parsed["implementation"],
                    _json(parsed["config"]),
                    kind,
                    name,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"unknown {kind}: {name}")
        return self.get(kind, name)

    def delete(self, kind: DefinitionKind, name: str) -> None:
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT is_builtin FROM research_definitions WHERE kind=? AND name=?",
                (kind, name),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown {kind}: {name}")
            if bool(row[0]):
                raise ValueError(f"built-in {kind} cannot be deleted: {name}")
            connection.execute(
                "DELETE FROM research_definitions WHERE kind=? AND name=?", (kind, name)
            )


def validate_definition_name(name: str) -> str:
    normalized = name.strip().lower()
    if not NAME_PATTERN.fullmatch(normalized):
        raise ValueError("name must use 3-64 lowercase letters, digits, or underscores")
    return normalized


def parse_definition_code(kind: DefinitionKind, code: str) -> dict[str, Any]:
    variable = "STRATEGY" if kind == "strategy" else "FACTOR"
    payload = _literal_assignment(code, variable)
    title = _required_text(payload, "title")
    description = _required_text(payload, "description")
    config: dict[str, Any]
    if kind == "strategy":
        implementation = _required_text(payload, "type")
        if implementation not in STRATEGY_TYPES:
            raise ValueError(f"unsupported strategy type: {implementation}")
        parameters = payload.get("parameters", {})
        if not isinstance(parameters, dict):
            raise ValueError("strategy parameters must be a dictionary")
        config = {"parameters": parameters}
    else:
        implementation = "expression"
        expression = _required_text(payload, "expression")
        input_fields = payload.get("input_fields")
        if not isinstance(input_fields, (list, tuple)) or not input_fields:
            raise ValueError("factor input_fields must be a non-empty list")
        normalized_fields = [str(item) for item in input_fields]
        unknown = set(normalized_fields) - BAR_FIELDS
        if unknown:
            raise ValueError(f"unknown factor input fields: {sorted(unknown)}")
        lookback = payload.get("lookback")
        if not isinstance(lookback, int) or lookback < 1:
            raise ValueError("factor lookback must be a positive integer")
        frequency = str(payload.get("frequency", "1d"))
        if frequency not in {"1d", "1m", "5m", "15m", "30m", "1h"}:
            raise ValueError(f"unsupported factor frequency: {frequency}")
        config = {
            "expression": expression,
            "input_fields": normalized_fields,
            "lookback": lookback,
            "frequency": frequency,
            "higher_is_better": bool(payload.get("higher_is_better", True)),
        }
    return {
        "title": title,
        "description": description,
        "implementation": implementation,
        "config": config,
    }


def _literal_assignment(code: str, variable: str) -> dict[str, Any]:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"invalid definition syntax: {exc.msg} (line {exc.lineno})") from exc
    body = [node for node in tree.body if not isinstance(node, ast.Expr) or not _is_docstring(node)]
    if len(body) != 1 or not isinstance(body[0], ast.Assign):
        raise ValueError(f"code must contain one literal {variable} assignment")
    assignment = body[0]
    if len(assignment.targets) != 1 or not isinstance(assignment.targets[0], ast.Name):
        raise ValueError(f"code must assign a literal dictionary to {variable}")
    if assignment.targets[0].id != variable:
        raise ValueError(f"code must assign to {variable}")
    try:
        payload = ast.literal_eval(assignment.value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{variable} must be a literal dictionary") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{variable} must be a dictionary")
    return cast(dict[str, Any], payload)


def _is_docstring(node: ast.Expr) -> bool:
    return isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def _builtin_definitions() -> tuple[tuple[DefinitionKind, str, str], ...]:
    return (
        ("strategy", "moving_average_cross", MOVING_AVERAGE_CODE),
        ("strategy", "buy_and_hold", BUY_AND_HOLD_CODE),
        ("factor", "momentum_20", MOMENTUM_FACTOR_CODE),
        ("factor", "volatility_20", VOLATILITY_FACTOR_CODE),
        ("factor", "average_turnover_20", TURNOVER_FACTOR_CODE),
    )


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _record(row: tuple[Any, ...]) -> ResearchDefinition:
    return ResearchDefinition(
        kind=cast(DefinitionKind, str(row[0])),
        name=str(row[1]),
        title=str(row[2]),
        description=str(row[3]),
        code=str(row[4]),
        implementation=str(row[5]),
        config=cast(dict[str, Any], json.loads(str(row[6]))),
        version=int(row[7]),
        is_builtin=bool(row[8]),
        created_at=str(row[9]),
        updated_at=str(row[10]),
    )
