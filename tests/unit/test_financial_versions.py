import json
import sqlite3
from pathlib import Path

from dyadresearch.config import DataConfig
from dyadresearch.data.financial import FinancialReader


def test_point_in_time_selects_whole_latest_report_version(tmp_path: Path) -> None:
    path = tmp_path / "fundamentals_2024.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE financial_records("
            "symbol TEXT, table_name TEXT, report_date INTEGER, announcement_date INTEGER, "
            "row_ordinal INTEGER, raw_json TEXT, source TEXT, ingested_at INTEGER, "
            "source_hash TEXT, "
            "PRIMARY KEY(symbol, table_name, report_date, announcement_date, row_ordinal))"
        )
        rows = [
            ("000001.SZ", "Income", 20240331, 20240420, 0, {"value": "old-0"}),
            ("000001.SZ", "Income", 20240331, 20240420, 1, {"value": "old-1"}),
            ("000001.SZ", "Income", 20240331, 20240425, 0, {"value": "new-0"}),
        ]
        connection.executemany(
            "INSERT INTO financial_records VALUES (?, ?, ?, ?, ?, ?, 'test', 1, ?)",
            [(*row[:5], json.dumps(row[5]), f"hash-{index}") for index, row in enumerate(rows)],
        )
    reader = FinancialReader(DataConfig(tmp_path))
    old = reader.as_of(
        ["000001.SZ"],
        table_names=["Income"],
        as_of_date=20240420,
        earliest_report_date=20240101,
    )
    revised = reader.as_of(
        ["000001.SZ"],
        table_names=["Income"],
        as_of_date=20240425,
        earliest_report_date=20240101,
    )
    assert [item.values["value"] for item in old] == ["old-0", "old-1"]
    assert [item.values["value"] for item in revised] == ["new-0"]
