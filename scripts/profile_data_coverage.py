from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def profile(root: Path) -> dict[str, Any]:
    catalog_path = root / "catalog.db"
    with sqlite3.connect(catalog_path) as connection:
        instruments = {
            str(kind): int(count)
            for kind, count in connection.execute(
                "SELECT COALESCE(instrument_type, 'unknown'), count(*) "
                "FROM instruments GROUP BY instrument_type ORDER BY instrument_type"
            )
        }
        watermarks = [
            {
                "dataset": str(row[0]),
                "period": str(row[1]),
                "symbols": int(row[2]),
                "rows": int(row[3]),
                "first_ts": None if row[4] is None else int(row[4]),
                "last_ts": None if row[5] is None else int(row[5]),
            }
            for row in connection.execute(
                "SELECT dataset, period, count(*), sum(row_count), min(first_ts), max(last_ts) "
                "FROM dataset_watermarks GROUP BY dataset, period ORDER BY dataset, period"
            )
        ]
        etf_watermarks = [
            {
                "period": str(row[0]),
                "symbols": int(row[1]),
                "rows": int(row[2]),
                "first_ts": None if row[3] is None else int(row[3]),
                "last_ts": None if row[4] is None else int(row[4]),
            }
            for row in connection.execute(
                "SELECT w.period, count(*), sum(w.row_count), min(w.first_ts), max(w.last_ts) "
                "FROM dataset_watermarks w JOIN instruments i ON i.symbol=w.symbol "
                "WHERE w.dataset='bars' AND i.instrument_type='etf' GROUP BY w.period "
                "ORDER BY w.period"
            )
        ]
        reference = {
            "sector_memberships": int(
                connection.execute("SELECT count(*) FROM sector_snapshots").fetchone()[0]
            ),
            "sector_snapshot_dates": [
                int(row[0])
                for row in connection.execute(
                    "SELECT DISTINCT snapshot_date FROM sector_snapshots ORDER BY snapshot_date"
                )
            ],
            "index_weight_components": int(
                connection.execute("SELECT count(*) FROM index_weight_snapshots").fetchone()[0]
            ),
            "index_weight_snapshot_dates": [
                int(row[0])
                for row in connection.execute(
                    "SELECT DISTINCT snapshot_date FROM index_weight_snapshots "
                    "ORDER BY snapshot_date"
                )
            ],
        }
    financial: list[dict[str, Any]] = []
    for path in sorted(root.glob("fundamentals_*.db")):
        with sqlite3.connect(path) as connection:
            row = connection.execute(
                "SELECT count(*), count(DISTINCT symbol), count(DISTINCT table_name), "
                "min(NULLIF(report_date, 0)), max(NULLIF(report_date, 0)) "
                "FROM financial_records"
            ).fetchone()
            financial.append(
                {
                    "database": path.name,
                    "rows": int(row[0]),
                    "symbols": int(row[1]),
                    "tables": int(row[2]),
                    "first_report_date": None if row[3] is None else int(row[3]),
                    "last_report_date": None if row[4] is None else int(row[4]),
                }
            )
    return {
        "root": str(root.resolve()),
        "database_count": len(list(root.glob("*.db"))),
        "instruments": instruments,
        "watermarks": watermarks,
        "etf_watermarks": etf_watermarks,
        "financial": financial,
        "reference": reference,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile migrated DyadResearch SQLite coverage")
    parser.add_argument("--root", type=Path, default=Path("data/sqlite"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = profile(args.root)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
