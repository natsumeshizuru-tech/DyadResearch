from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

FORBIDDEN_MODULE_PREFIXES = ("dyadtetrade", "xtquant.xttrader")
FORBIDDEN_NAMES = {"XtTrader", "XtQuantTrader", "TradingEngine", "LiveTradingGateway"}


@dataclass(frozen=True, slots=True)
class ImportViolation:
    path: str
    line: int
    reason: str


def scan_forbidden_imports(root: Path) -> tuple[ImportViolation, ...]:
    violations: list[ImportViolation] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(FORBIDDEN_MODULE_PREFIXES):
                        violations.append(
                            ImportViolation(
                                str(path), node.lineno, f"forbidden import {alias.name}"
                            )
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith(FORBIDDEN_MODULE_PREFIXES):
                    violations.append(
                        ImportViolation(str(path), node.lineno, f"forbidden import {module}")
                    )
                for alias in node.names:
                    if alias.name in FORBIDDEN_NAMES:
                        violations.append(
                            ImportViolation(str(path), node.lineno, f"forbidden name {alias.name}")
                        )
    return tuple(violations)
