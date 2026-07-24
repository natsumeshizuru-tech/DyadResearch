from __future__ import annotations

import platform
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dyadresearch.config import ResearchConfig
from dyadresearch.data.capabilities import capability_matrix
from dyadresearch.data.sqlite import readonly_connection
from dyadresearch.safety import scan_forbidden_imports


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    ok: bool
    detail: str


def run_doctor(config: ResearchConfig, *, source_root: Path | None = None) -> dict[str, Any]:
    checks = [
        Check("python", sys.version_info >= (3, 12), platform.python_version()),
        Check("sqlite", sqlite3.sqlite_version_info >= (3, 35), sqlite3.sqlite_version),
        Check("data_root", config.data.root.is_dir(), str(config.data.root)),
        Check("readonly_config", config.data.readonly, "must always be true"),
    ]
    for name in (config.data.catalog, config.data.daily_bars):
        path = config.data.root / name
        ok, detail = _database_check(path, config.data.busy_timeout_ms)
        checks.append(Check(f"database:{name}", ok, detail))
    package_root = source_root or Path(__file__).resolve().parent
    violations = scan_forbidden_imports(package_root)
    checks.append(
        Check(
            "no_trading_imports",
            not violations,
            "none" if not violations else "; ".join(v.reason for v in violations),
        )
    )
    return {
        "ok": all(check.ok for check in checks),
        "checks": [asdict(check) for check in checks],
        "capabilities": capability_matrix(config.data.root),
    }


def _database_check(path: Path, timeout: int) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"missing: {path}"
    try:
        with readonly_connection(path, busy_timeout_ms=timeout) as connection:
            query_only = int(connection.execute("PRAGMA query_only").fetchone()[0])
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        return query_only == 1, f"query_only={query_only}, user_version={version}"
    except sqlite3.Error as exc:
        return False, str(exc)
