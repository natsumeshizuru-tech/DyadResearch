from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

SAMPLE_SYMBOLS = (
    ("000001.SZ", "Synthetic SZ Main Board", "SZ", "stock"),
    ("600001.SH", "Synthetic SH Main Board", "SH", "stock"),
    ("510300.SH", "Synthetic CSI 300 ETF", "SH", "etf"),
    ("510500.SH", "Synthetic CSI 500 ETF", "SH", "etf"),
    ("159915.SZ", "Synthetic Growth ETF", "SZ", "etf"),
)
FIXED_INGESTED_AT = 20260719000000


def generate_sample_data(root: Path, *, overwrite: bool = False) -> dict[str, Any]:
    """Generate a small deterministic SQLite demo marked as synthetic data."""

    output = root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    marker_path = output / "SYNTHETIC_DATA.json"
    targets = {
        "catalog": output / "catalog.db",
        "daily": output / "bars_1d.db",
        "financial": output / "fundamentals_2024.db",
    }
    if not overwrite and all(path.is_file() for path in targets.values()):
        if _is_synthetic_marker(marker_path):
            return _manifest(output, targets, generated=False)
        raise FileExistsError(
            f"refusing to treat existing unmarked databases as demo data: {output}"
        )
    existing_targets = [path for path in targets.values() if path.exists()]
    if overwrite and existing_targets and not _is_synthetic_marker(marker_path):
        raise ValueError(
            f"refusing to overwrite databases without a valid SYNTHETIC DATA marker: {output}"
        )
    for path in targets.values():
        if path.exists():
            if not overwrite:
                raise FileExistsError(f"partial sample dataset exists: {path}")
            path.unlink()

    dates = _business_days(date(2024, 1, 2), 60)
    _write_catalog(targets["catalog"], dates)
    _write_daily_bars(targets["daily"], dates)
    _write_financials(targets["financial"])
    marker = {
        "classification": "SYNTHETIC DATA",
        "seed": 0,
        "symbols": [item[0] for item in SAMPLE_SYMBOLS],
        "start": dates[0].isoformat(),
        "end": dates[-1].isoformat(),
        "edge_cases": [
            "suspension",
            "limit-up-like bar",
            "cash dividend",
            "financial announcement revision",
            "cross-month dates",
        ],
    }
    marker_path.write_text(
        json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return _manifest(output, targets, generated=True)


def _is_synthetic_marker(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(payload, dict):
        return False
    classification = payload.get("classification")
    return isinstance(classification, str) and classification == "SYNTHETIC DATA"


def _business_days(start: date, count: int) -> list[date]:
    values: list[date] = []
    current = start
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current)
        current += timedelta(days=1)
    return values


def _write_catalog(path: Path, dates: list[date]) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA user_version=1;
            CREATE TABLE instruments(
                symbol TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                market TEXT NOT NULL,
                name TEXT NOT NULL,
                instrument_type TEXT NOT NULL,
                list_date INTEGER,
                delist_date INTEGER,
                is_active INTEGER NOT NULL,
                price_tick TEXT,
                volume_multiple INTEGER,
                raw_json TEXT NOT NULL,
                source TEXT NOT NULL,
                first_seen_at INTEGER NOT NULL,
                last_seen_at INTEGER NOT NULL
            );
            CREATE TABLE trading_calendar(
                market TEXT NOT NULL,
                trade_date INTEGER NOT NULL,
                is_open INTEGER NOT NULL,
                prev_trade_date INTEGER,
                next_trade_date INTEGER,
                source TEXT NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY(market, trade_date)
            );
            CREATE TABLE corporate_actions(
                symbol TEXT NOT NULL,
                action_date INTEGER NOT NULL,
                interest REAL NOT NULL,
                stock_bonus REAL NOT NULL,
                stock_gift REAL NOT NULL,
                allot_num REAL NOT NULL,
                allot_price REAL NOT NULL,
                gugai INTEGER NOT NULL,
                dr REAL NOT NULL,
                raw_json TEXT,
                source TEXT NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY(symbol, action_date)
            );
            CREATE TABLE sector_snapshots(
                snapshot_date INTEGER NOT NULL,
                sector_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                source TEXT NOT NULL,
                PRIMARY KEY(snapshot_date, sector_name, symbol)
            );
            CREATE TABLE index_weight_snapshots(
                snapshot_date INTEGER NOT NULL,
                index_code TEXT NOT NULL,
                symbol TEXT NOT NULL,
                weight REAL NOT NULL,
                source TEXT NOT NULL,
                PRIMARY KEY(snapshot_date, index_code, symbol)
            );
            CREATE TABLE dataset_watermarks(
                dataset TEXT NOT NULL,
                period TEXT NOT NULL,
                symbol TEXT NOT NULL,
                first_ts INTEGER,
                last_ts INTEGER,
                row_count INTEGER NOT NULL,
                last_success_job_id TEXT,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY(dataset, period, symbol)
            );
            CREATE TABLE sector_catalog(
                snapshot_date INTEGER NOT NULL,
                sector_name TEXT NOT NULL,
                total_member_count INTEGER NOT NULL,
                a_share_member_count INTEGER NOT NULL,
                source TEXT NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY(snapshot_date, sector_name)
            );
            CREATE TABLE index_weight_catalog(
                snapshot_date INTEGER NOT NULL,
                index_code TEXT NOT NULL,
                total_component_count INTEGER NOT NULL,
                a_share_component_count INTEGER NOT NULL,
                total_weight REAL NOT NULL,
                source TEXT NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY(snapshot_date, index_code)
            );
            """
        )
        connection.executemany(
            "INSERT INTO instruments VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    symbol,
                    symbol.split(".", 1)[0],
                    exchange,
                    name,
                    asset_type,
                    20200101,
                    None,
                    1,
                    "0.01",
                    100,
                    '{"classification":"SYNTHETIC"}',
                    "SYNTHETIC",
                    FIXED_INGESTED_AT,
                    FIXED_INGESTED_AT,
                )
                for symbol, name, exchange, asset_type in SAMPLE_SYMBOLS
            ],
        )
        connection.executemany(
            "INSERT INTO trading_calendar VALUES(?,?,?,?,?,?,?)",
            [
                (
                    market,
                    int(day.strftime("%Y%m%d")),
                    1,
                    int(dates[index - 1].strftime("%Y%m%d")) if index else None,
                    int(dates[index + 1].strftime("%Y%m%d")) if index + 1 < len(dates) else None,
                    "SYNTHETIC",
                    FIXED_INGESTED_AT,
                )
                for index, day in enumerate(dates)
                for market in ("SH", "SZ")
            ],
        )
        connection.execute(
            "INSERT INTO corporate_actions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "510300.SH",
                20240201,
                0.05,
                0,
                0,
                0,
                0,
                0,
                1,
                '{"classification":"SYNTHETIC"}',
                "SYNTHETIC",
                FIXED_INGESTED_AT,
            ),
        )
        connection.executemany(
            "INSERT INTO sector_snapshots VALUES(?,?,?,?)",
            [
                (20240325, "SYNTHETIC_MAIN_BOARD", symbol, "SYNTHETIC")
                for symbol, *_ in SAMPLE_SYMBOLS[:2]
            ],
        )
        connection.executemany(
            "INSERT INTO index_weight_snapshots VALUES(?,?,?,?,?)",
            [
                (20240325, "SYNTHETIC_INDEX", "000001.SZ", 0.5, "SYNTHETIC"),
                (20240325, "SYNTHETIC_INDEX", "600001.SH", 0.5, "SYNTHETIC"),
            ],
        )
        first_ts = int(dates[0].strftime("%Y%m%d"))
        last_ts = int(dates[-1].strftime("%Y%m%d"))
        connection.executemany(
            "INSERT INTO dataset_watermarks VALUES(?,?,?,?,?,?,?,?)",
            [
                (
                    "bars",
                    "1d",
                    symbol,
                    first_ts,
                    last_ts,
                    len(dates),
                    "SYNTHETIC",
                    FIXED_INGESTED_AT,
                )
                for symbol, *_ in SAMPLE_SYMBOLS
            ],
        )
        connection.execute(
            "INSERT INTO sector_catalog VALUES(?,?,?,?,?,?)",
            (last_ts, "SYNTHETIC_MAIN_BOARD", 2, 2, "SYNTHETIC", FIXED_INGESTED_AT),
        )
        connection.execute(
            "INSERT INTO index_weight_catalog VALUES(?,?,?,?,?,?,?)",
            (last_ts, "SYNTHETIC_INDEX", 2, 2, 1.0, "SYNTHETIC", FIXED_INGESTED_AT),
        )


def _write_daily_bars(path: Path, dates: list[date]) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA user_version=1;
            CREATE TABLE bars(
                symbol TEXT NOT NULL,
                ts INTEGER NOT NULL,
                trade_date INTEGER NOT NULL,
                open TEXT,
                high TEXT,
                low TEXT,
                close TEXT,
                volume INTEGER NOT NULL,
                amount TEXT,
                settlement_price TEXT,
                open_interest TEXT,
                pre_close TEXT,
                suspend_flag INTEGER NOT NULL,
                source TEXT NOT NULL,
                ingested_at INTEGER NOT NULL,
                source_hash TEXT,
                PRIMARY KEY(symbol, ts)
            );
            CREATE INDEX idx_bars_trade_date_symbol ON bars(trade_date, symbol);
            """
        )
        rows: list[tuple[object, ...]] = []
        for symbol_index, (symbol, *_rest) in enumerate(SAMPLE_SYMBOLS):
            previous = Decimal("8") + Decimal(symbol_index * 2)
            for day_index, day in enumerate(dates):
                trade_date = int(day.strftime("%Y%m%d"))
                suspended = symbol == "600001.SH" and day_index == 12
                drift = Decimal(((day_index + symbol_index * 3) % 9) - 4) / Decimal("500")
                close = (
                    previous
                    if suspended
                    else (previous * (Decimal("1") + drift)).quantize(Decimal("0.001"))
                )
                if symbol == "000001.SZ" and day_index == 20:
                    close = (previous * Decimal("1.099")).quantize(Decimal("0.001"))
                open_price = (
                    previous
                    if suspended
                    else (previous * Decimal("1.001")).quantize(Decimal("0.001"))
                )
                high = max(open_price, close) * Decimal("1.005")
                low = min(open_price, close) * Decimal("0.995")
                volume = 0 if suspended else 100_000 + symbol_index * 10_000 + day_index * 1_000
                amount = (close * volume).quantize(Decimal("0.01"))
                source_hash = hashlib.sha256(
                    f"SYNTHETIC|{symbol}|{trade_date}|{close}".encode()
                ).hexdigest()
                rows.append(
                    (
                        symbol,
                        trade_date,
                        trade_date,
                        str(open_price),
                        str(high.quantize(Decimal("0.001"))),
                        str(low.quantize(Decimal("0.001"))),
                        str(close),
                        volume,
                        str(amount),
                        None,
                        None,
                        str(previous),
                        int(suspended),
                        "SYNTHETIC",
                        FIXED_INGESTED_AT,
                        source_hash,
                    )
                )
                previous = close
        connection.executemany("INSERT INTO bars VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)


def _write_financials(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            PRAGMA user_version=1;
            CREATE TABLE financial_records(
                symbol TEXT NOT NULL,
                table_name TEXT NOT NULL,
                report_date INTEGER NOT NULL,
                announcement_date INTEGER NOT NULL,
                row_ordinal INTEGER NOT NULL,
                raw_json TEXT NOT NULL,
                source TEXT NOT NULL,
                ingested_at INTEGER NOT NULL,
                source_hash TEXT NOT NULL
            );
            """
        )
        rows = []
        for symbol, *_ in SAMPLE_SYMBOLS[:2]:
            for announcement, revenue in ((20240131, 100), (20240220, 103)):
                payload = json.dumps(
                    {"revenue": revenue, "classification": "SYNTHETIC"}, sort_keys=True
                )
                rows.append(
                    (
                        symbol,
                        "Income",
                        20231231,
                        announcement,
                        0,
                        payload,
                        "SYNTHETIC",
                        FIXED_INGESTED_AT,
                        hashlib.sha256(payload.encode()).hexdigest(),
                    )
                )
        connection.executemany("INSERT INTO financial_records VALUES(?,?,?,?,?,?,?,?,?)", rows)


def _manifest(root: Path, targets: dict[str, Path], *, generated: bool) -> dict[str, Any]:
    return {
        "ok": True,
        "classification": "SYNTHETIC DATA",
        "generated": generated,
        "root": str(root),
        "files": {name: path.name for name, path in targets.items()},
        "symbols": [item[0] for item in SAMPLE_SYMBOLS],
        "orders_sent": 0,
    }
