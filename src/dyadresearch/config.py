from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from dyadresearch.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class DataConfig:
    root: Path
    readonly: bool = True
    catalog: str = "catalog.db"
    daily_bars: str = "bars_1d.db"
    minute_pattern: str = "bars_1m_{market}_{year_month}.db"
    fundamentals_pattern: str = "fundamentals_{year}.db"
    busy_timeout_ms: int = 60_000
    immutable: bool = False

    def __post_init__(self) -> None:
        if not self.readonly:
            raise ConfigurationError("source SQLite data must be configured readonly")
        if self.busy_timeout_ms < 0:
            raise ConfigurationError("busy_timeout_ms cannot be negative")


@dataclass(frozen=True, slots=True)
class ResearchPaths:
    database: Path = Path("research.db")
    reports_root: Path = Path("reports/generated")


@dataclass(frozen=True, slots=True)
class BacktestDefaults:
    policy: str = "strict_research"
    initial_cash: Decimal = Decimal("1000000")
    result_root: Path = Path("reports/backtests")
    random_seed: int = 0


@dataclass(frozen=True, slots=True)
class ResearchConfig:
    name: str
    timezone: str
    data: DataConfig
    research: ResearchPaths
    backtest: BacktestDefaults


def load_config(path: str | Path = Path("config/research.yaml")) -> ResearchConfig:
    config_path = Path(path)
    if not config_path.exists() and config_path.name == "research.yaml":
        public_example = config_path.with_name("research.example.yaml")
        if public_example.is_file():
            config_path = public_example
    if not config_path.exists():
        raise ConfigurationError(f"configuration does not exist: {config_path}")
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ConfigurationError("configuration root must be a mapping")
    project = _mapping(payload, "project")
    data = _mapping(payload, "data")
    research = _mapping(payload, "research")
    backtest = _mapping(payload, "backtest")
    return ResearchConfig(
        name=str(project.get("name", "DyadResearch")),
        timezone=str(project.get("timezone", "Asia/Shanghai")),
        data=DataConfig(
            root=Path(str(_required(data, "root"))),
            readonly=bool(data.get("readonly", True)),
            catalog=str(data.get("catalog", "catalog.db")),
            daily_bars=str(data.get("daily_bars", "bars_1d.db")),
            minute_pattern=str(data.get("minute_pattern", "bars_1m_{market}_{year_month}.db")),
            fundamentals_pattern=str(data.get("fundamentals_pattern", "fundamentals_{year}.db")),
            busy_timeout_ms=int(data.get("busy_timeout_ms", 60_000)),
            immutable=bool(data.get("immutable", False)),
        ),
        research=ResearchPaths(
            database=Path(str(research.get("database", "research.db"))),
            reports_root=Path(str(research.get("reports_root", "reports/generated"))),
        ),
        backtest=BacktestDefaults(
            policy=str(backtest.get("policy", "strict_research")),
            initial_cash=Decimal(str(backtest.get("initial_cash", "1000000"))),
            result_root=Path(str(backtest.get("result_root", "reports/backtests"))),
            random_seed=int(backtest.get("random_seed", 0)),
        ),
    )


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"{key} must be a mapping")
    return value


def _required(payload: dict[str, Any], key: str) -> Any:
    if key not in payload:
        raise ConfigurationError(f"missing required configuration key: {key}")
    return payload[key]
