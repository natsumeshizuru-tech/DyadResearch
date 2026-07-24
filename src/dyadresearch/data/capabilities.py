from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dyadresearch.data.aggregation import DAILY_PERIODS, MINUTE_SIZES
from dyadresearch.errors import DataCapabilityError


@dataclass(frozen=True, slots=True)
class Capability:
    dataset: str
    available_from: int | None
    available_to: int | None
    complete: bool
    reason: str


CAPABILITIES = (
    Capability(
        "bars:1d",
        20100104,
        20260717,
        True,
        "lifecycle-aware local SQLite coverage for stocks, ETFs, and indices",
    ),
    Capability(
        "bars:derived_daily",
        20100104,
        20260717,
        True,
        "1w/1mon/1q/1hy/1y are deterministically synthesized from validated 1d bars",
    ),
    Capability(
        "bars:1m:SH_SZ",
        20250711,
        20260717,
        False,
        "upstream QMT cache has no earlier minute history",
    ),
    Capability(
        "bars:1m:BJ", 20250716, 20260717, False, "upstream QMT cache has no earlier minute history"
    ),
    Capability(
        "bars:derived_minute",
        20250711,
        20260717,
        False,
        "5m/15m/30m/1h are synthesized from truthful local 1m bars; upstream has no earlier rows",
    ),
    Capability(
        "bars:index_etf",
        20100104,
        20260717,
        True,
        "current QMT ETF and index instruments are covered over their listing lifecycles; "
        "unlaunched placeholder contracts are excluded",
    ),
    Capability("financial", 20100101, 20260717, True, "eight point-in-time local financial tables"),
    Capability(
        "sector_membership", 20260717, 20260717, False, "only the 2026-07-17 snapshot is available"
    ),
    Capability(
        "index_weights", 20260717, 20260717, False, "only the 2026-07-17 snapshot is available"
    ),
    Capability(
        "delisted_universe",
        20100101,
        20260717,
        True,
        "285 SSE/SZSE official delisted lifecycles are cataloged; xtdata returned bars for "
        "282 and explicit audited empty results for 3",
    ),
)


def _database_date_range(path: Path) -> tuple[int, int] | None:
    """Read the truthful bar range without ever creating or mutating a database."""
    if not path.is_file():
        return None
    try:
        uri = f"{path.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=1.0) as connection:
            first = connection.execute("SELECT MIN(trade_date) FROM bars").fetchone()
            last = connection.execute("SELECT MAX(trade_date) FROM bars").fetchone()
    except (OSError, sqlite3.Error):
        return None
    if first is None or last is None or first[0] is None or last[0] is None:
        return None
    return int(first[0]), int(last[0])


def _merged_date_range(paths: list[Path]) -> tuple[int, int] | None:
    first: tuple[int, int] | None = None
    first_path: Path | None = None
    for path in paths:
        if (date_range := _database_date_range(path)) is not None:
            first = date_range
            first_path = path
            break
    if first is None:
        return None
    for path in reversed(paths):
        if path == first_path:
            return first
        if (last := _database_date_range(path)) is not None:
            return first[0], last[1]
    return first


def _bar_ranges(data_root: Path) -> dict[str, tuple[int, int] | None]:
    minute_paths = sorted(data_root.glob("bars_1m_*.db"))
    sh_sz_paths = [path for path in minute_paths if "_SH_" in path.name or "_SZ_" in path.name]
    bj_paths = [path for path in minute_paths if "_BJ_" in path.name]
    return {
        "daily": _database_date_range(data_root / "bars_1d.db"),
        "minute": _merged_date_range(minute_paths),
        "minute_sh_sz": _merged_date_range(sh_sz_paths),
        "minute_bj": _merged_date_range(bj_paths),
    }


def _runtime_capabilities(data_root: Path) -> tuple[Capability, ...]:
    ranges = _bar_ranges(data_root)
    daily = ranges["daily"]
    minute = ranges["minute"]
    minute_sh_sz = ranges["minute_sh_sz"]
    minute_bj = ranges["minute_bj"]
    result: list[Capability] = []
    for item in CAPABILITIES:
        date_range: tuple[int, int] | None = None
        if item.dataset in {"bars:1d", "bars:derived_daily", "bars:index_etf"}:
            date_range = daily
        elif item.dataset == "bars:1m:SH_SZ":
            date_range = minute_sh_sz
        elif item.dataset == "bars:1m:BJ":
            date_range = minute_bj
        elif item.dataset == "bars:derived_minute":
            date_range = minute
        if date_range is None:
            result.append(item)
        else:
            result.append(
                Capability(
                    item.dataset,
                    date_range[0],
                    date_range[1],
                    item.complete,
                    item.reason,
                )
            )
    return tuple(result)


def capability_matrix(data_root: Path | None = None) -> list[dict[str, Any]]:
    if data_root is not None:
        marker = data_root / "SYNTHETIC_DATA.json"
        if marker.is_file():
            payload = json.loads(marker.read_text(encoding="utf-8"))
            start = int(str(payload["start"]).replace("-", ""))
            end = int(str(payload["end"]).replace("-", ""))
            sample = (
                Capability(
                    "bars:1d",
                    start,
                    end,
                    True,
                    "deterministic public SYNTHETIC DATA; not vendor market history",
                ),
                Capability(
                    "financial",
                    20231231,
                    20240220,
                    True,
                    "synthetic point-in-time announcement and revision examples",
                ),
                Capability(
                    "sector_membership",
                    end,
                    end,
                    False,
                    "one synthetic exact-date snapshot",
                ),
                Capability(
                    "index_weights",
                    end,
                    end,
                    False,
                    "one synthetic exact-date snapshot",
                ),
            )
            return [asdict(item) for item in sample]
        return [asdict(item) for item in _runtime_capabilities(data_root)]
    return [asdict(item) for item in CAPABILITIES]


def require_bar_capability(
    period: str,
    symbols: list[str],
    start: int,
    end: int,
    *,
    data_root: Path | None = None,
) -> None:
    if start > end:
        raise ValueError("start must not exceed end")
    raw_period = "1m" if period in MINUTE_SIZES else "1d" if period in DAILY_PERIODS else period
    if raw_period == "1d":
        lower, upper = 20100104, 20260717
        if data_root is not None and (date_range := _database_date_range(data_root / "bars_1d.db")):
            lower, upper = date_range
    elif raw_period == "1m":
        bj_only = bool(symbols) and all(s.upper().endswith(".BJ") for s in symbols)
        lower = 20250716 if bj_only else 20250711
        upper = 20260717
        if data_root is not None:
            paths = sorted(data_root.glob("bars_1m_*.db"))
            market_token = "_BJ_" if bj_only else ("_SH_", "_SZ_")
            if isinstance(market_token, tuple):
                paths = [
                    path for path in paths if any(token in path.name for token in market_token)
                ]
            else:
                paths = [path for path in paths if market_token in path.name]
            date_range = _merged_date_range(paths)
            if date_range is not None:
                lower, upper = date_range
    else:
        raise DataCapabilityError(f"unsupported period: {period}")
    if start < lower or end > upper:
        raise DataCapabilityError(
            f"requested {period} range {start}..{end} exceeds truthful local "
            f"coverage {lower}..{upper}"
        )
