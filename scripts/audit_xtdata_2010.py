from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

DOCUMENTED_EMPTY_DAILY_RULES = (
    "qmt_etf_placeholder_without_listed_history",
    "upstream_xtdata_delisted_history_unavailable",
    "upstream_xtdata_index_history_unavailable",
)


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:///{path.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return {str(key): row[key] for key in row.keys()}  # noqa: SIM118


def audit(
    root: Path,
    *,
    start: int,
    end: int,
    official_universe_report: Path | None = None,
) -> dict[str, Any]:
    catalog_path = root / "catalog.db"
    daily_path = root / "bars_1d.db"
    if not catalog_path.is_file() or not daily_path.is_file():
        raise FileNotFoundError("catalog.db and bars_1d.db are required")

    with _connect(catalog_path) as catalog:
        instruments = [
            _row(row)
            for row in catalog.execute(
                "SELECT instrument_type, is_active, count(*) AS symbols, "
                "min(list_date) AS first_list_date, max(list_date) AS last_list_date "
                "FROM instruments GROUP BY instrument_type, is_active "
                "ORDER BY instrument_type, is_active"
            )
        ]
        daily_watermarks = [
            _row(row)
            for row in catalog.execute(
                "SELECT i.instrument_type, i.is_active, count(*) AS symbols, "
                "sum(w.row_count) AS rows, min(w.first_ts) AS first_ts, "
                "max(w.last_ts) AS last_ts "
                "FROM dataset_watermarks AS w "
                "JOIN instruments AS i ON i.symbol=w.symbol "
                "WHERE w.dataset='bars' AND w.period='1d' "
                "GROUP BY i.instrument_type, i.is_active "
                "ORDER BY i.instrument_type, i.is_active"
            )
        ]
        missing_active_watermarks = [
            _row(row)
            for row in catalog.execute(
                "SELECT i.instrument_type, count(*) AS symbols "
                "FROM instruments AS i "
                "LEFT JOIN dataset_watermarks AS w ON w.symbol=i.symbol "
                "AND w.dataset='bars' AND w.period='1d' "
                "WHERE i.is_active=1 AND (i.list_date IS NULL OR i.list_date<=?) "
                "AND w.symbol IS NULL "
                "GROUP BY i.instrument_type ORDER BY i.instrument_type",
                (end,),
            )
        ]
        missing_scoped_watermarks = [
            _row(row)
            for row in catalog.execute(
                "SELECT i.instrument_type, count(*) AS symbols "
                "FROM instruments AS i "
                "LEFT JOIN dataset_watermarks AS w ON w.symbol=i.symbol "
                "AND w.dataset='bars' AND w.period='1d' "
                "WHERE i.instrument_type IN ('stock','etf','index') "
                "AND (i.list_date IS NULL OR i.list_date<=?) "
                "AND (i.delist_date IS NULL OR i.delist_date>=?) "
                "AND w.symbol IS NULL AND NOT EXISTS ("
                "SELECT 1 FROM data_quality_issues AS q "
                "JOIN job_items AS j ON j.job_id=q.job_id AND j.symbol=q.symbol "
                "WHERE q.symbol=i.symbol "
                "AND q.rule IN (?,?,?) "
                "AND q.resolved_at IS NULL "
                "AND ((q.rule=? AND i.instrument_type='etf') "
                "OR (q.rule=? AND i.instrument_type='stock') "
                "OR (q.rule=? AND i.instrument_type='index')) "
                "AND j.dataset='bars' AND j.period='1d' AND j.status='completed' "
                "AND j.requested_start<=? AND j.requested_end>=?"
                ") GROUP BY i.instrument_type ORDER BY i.instrument_type",
                (
                    end,
                    start,
                    *DOCUMENTED_EMPTY_DAILY_RULES,
                    *DOCUMENTED_EMPTY_DAILY_RULES,
                    start,
                    end,
                ),
            )
        ]
        documented_unavailable_rows = [
            _row(row)
            for row in catalog.execute(
                "SELECT DISTINCT i.symbol, q.rule FROM instruments AS i "
                "LEFT JOIN dataset_watermarks AS w ON w.symbol=i.symbol "
                "AND w.dataset='bars' AND w.period='1d' "
                "JOIN data_quality_issues AS q ON q.symbol=i.symbol "
                "JOIN job_items AS j ON j.job_id=q.job_id AND j.symbol=q.symbol "
                "WHERE i.instrument_type IN ('stock','etf','index') "
                "AND (i.list_date IS NULL OR i.list_date<=?) "
                "AND (i.delist_date IS NULL OR i.delist_date>=?) "
                "AND w.symbol IS NULL AND q.rule IN (?,?,?) "
                "AND q.resolved_at IS NULL "
                "AND ((q.rule=? AND i.instrument_type='etf') "
                "OR (q.rule=? AND i.instrument_type='stock') "
                "OR (q.rule=? AND i.instrument_type='index')) "
                "AND j.dataset='bars' AND j.period='1d' AND j.status='completed' "
                "AND j.requested_start<=? AND j.requested_end>=? "
                "ORDER BY q.rule, i.symbol",
                (
                    end,
                    start,
                    *DOCUMENTED_EMPTY_DAILY_RULES,
                    *DOCUMENTED_EMPTY_DAILY_RULES,
                    start,
                    end,
                ),
            )
        ]
        documented_unavailable_daily = sorted(
            {str(row["symbol"]) for row in documented_unavailable_rows}
        )
        documented_unavailable_by_rule: dict[str, list[str]] = {
            rule: sorted(
                str(row["symbol"]) for row in documented_unavailable_rows if row["rule"] == rule
            )
            for rule in DOCUMENTED_EMPTY_DAILY_RULES
        }
        missing_financial_checkpoints = int(
            catalog.execute(
                "SELECT count(*) FROM instruments AS i WHERE i.instrument_type='stock' "
                "AND (i.list_date IS NULL OR i.list_date<=?) "
                "AND (i.delist_date IS NULL OR i.delist_date>=?) "
                "AND NOT EXISTS (SELECT 1 FROM job_items AS j WHERE j.symbol=i.symbol "
                "AND j.dataset='fundamentals' AND j.period='financial' "
                "AND j.status='completed' AND j.effective_start<=? "
                "AND j.effective_end>=?)",
                (end, start, start, end),
            ).fetchone()[0]
        )
        official_payload: dict[str, Any] = {}
        official_missing_catalog: list[str] = []
        if official_universe_report is not None and official_universe_report.is_file():
            official_payload = json.loads(official_universe_report.read_text(encoding="utf-8"))
            for record in official_payload.get("records", []):
                row = catalog.execute(
                    "SELECT list_date, delist_date FROM instruments WHERE symbol=?",
                    (str(record.get("symbol")),),
                ).fetchone()
                if (
                    row is None
                    or int(row[0] or 0) != int(record.get("list_date") or 0)
                    or int(row[1] or 0) != int(record.get("delist_date") or 0)
                ):
                    official_missing_catalog.append(str(record.get("symbol")))
        actions = _row(
            catalog.execute(
                "SELECT count(*) AS rows, count(DISTINCT ca.symbol) AS symbols, "
                "min(ca.action_date) AS first_action_date, "
                "max(ca.action_date) AS last_action_date, "
                "sum(CASE WHEN i.list_date IS NOT NULL "
                "AND ca.action_date<i.list_date THEN 1 ELSE 0 END) AS prelisting_rows, "
                "sum(CASE WHEN (i.list_date IS NULL OR ca.action_date>=i.list_date) "
                "AND (ca.dr<=0 OR ca.dr IS NULL) THEN 1 ELSE 0 END) AS invalid_active_dr "
                "FROM corporate_actions AS ca "
                "LEFT JOIN instruments AS i ON i.symbol=ca.symbol"
            ).fetchone()
        )
        recent_jobs = [
            _row(row)
            for row in catalog.execute(
                "SELECT job_id, job_type, requested_start, requested_end, status, "
                "success_items, failed_items, inserted_rows, updated_rows, "
                "started_at, finished_at FROM job_runs "
                "ORDER BY started_at DESC LIMIT 20"
            )
        ]

    with _connect(daily_path) as daily:
        daily_integrity = str(daily.execute("PRAGMA quick_check").fetchone()[0])
        daily_summary = _row(
            daily.execute(
                "SELECT count(*) AS rows, count(DISTINCT symbol) AS symbols, "
                "min(trade_date) AS first_trade_date, max(trade_date) AS last_trade_date, "
                "sum(CASE WHEN open<0 OR high<0 OR low<0 OR close<0 THEN 1 ELSE 0 END) "
                "AS negative_price_rows, "
                "sum(CASE WHEN high<max(open, close, low) THEN 1 ELSE 0 END) "
                "AS invalid_high_rows, "
                "sum(CASE WHEN low>min(open, close, high) THEN 1 ELSE 0 END) "
                "AS invalid_low_rows, "
                "sum(CASE WHEN volume<0 THEN 1 ELSE 0 END) AS negative_volume_rows, "
                "sum(CASE WHEN amount<0 THEN 1 ELSE 0 END) AS negative_amount_rows, "
                "sum(CASE WHEN trade_date<? OR trade_date>? THEN 1 ELSE 0 END) "
                "AS out_of_scope_rows FROM bars",
                (start, end),
            ).fetchone()
        )
        daily_by_source = {
            str(row[0]): int(row[1])
            for row in daily.execute(
                "SELECT source, count(*) FROM bars GROUP BY source ORDER BY source"
            )
        }

    financial_years: list[dict[str, Any]] = []
    financial_tables: defaultdict[str, dict[str, int]] = defaultdict(
        lambda: {"rows": 0, "symbols": 0}
    )
    financial_table_symbols: defaultdict[str, set[str]] = defaultdict(set)
    financial_clean = True
    for path in sorted(root.glob("fundamentals_*.db")):
        year = int(path.stem.rsplit("_", 1)[-1])
        if year < start // 10_000 or year > end // 10_000:
            continue
        with _connect(path) as connection:
            integrity = str(connection.execute("PRAGMA quick_check").fetchone()[0])
            summary = _row(
                connection.execute(
                    "SELECT count(*) AS rows, count(DISTINCT symbol) AS symbols, "
                    "count(DISTINCT table_name) AS tables, "
                    "min(NULLIF(report_date, 0)) AS first_report_date, "
                    "max(NULLIF(report_date, 0)) AS last_report_date, "
                    "max(NULLIF(announcement_date, 0)) AS last_announcement_date, "
                    "sum(CASE WHEN report_date=0 AND announcement_date=0 "
                    "THEN 1 ELSE 0 END) AS undated_rows, "
                    "sum(CASE WHEN announcement_date>? THEN 1 ELSE 0 END) "
                    "AS future_announcement_rows, "
                    "sum(CASE WHEN json_valid(raw_json)=0 THEN 1 ELSE 0 END) "
                    "AS invalid_json_rows FROM financial_records",
                    (end,),
                ).fetchone()
            )
            financial_years.append(
                {"year": year, "database": path.name, "integrity": integrity, **summary}
            )
            financial_clean = (
                financial_clean
                and integrity == "ok"
                and all(
                    int(summary[key] or 0) == 0
                    for key in ("undated_rows", "future_announcement_rows", "invalid_json_rows")
                )
            )
            for row in connection.execute(
                "SELECT table_name, count(*) AS rows FROM financial_records GROUP BY table_name"
            ):
                table = financial_tables[str(row[0])]
                table["rows"] += int(row[1])
            for row in connection.execute(
                "SELECT DISTINCT table_name, symbol FROM financial_records"
            ):
                financial_table_symbols[str(row[0])].add(str(row[1]))

    for table_name, symbols in financial_table_symbols.items():
        financial_tables[table_name]["symbols"] = len(symbols)

    daily_clean = daily_integrity == "ok" and all(
        int(daily_summary[key] or 0) == 0
        for key in (
            "negative_price_rows",
            "invalid_high_rows",
            "invalid_low_rows",
            "negative_volume_rows",
            "negative_amount_rows",
            "out_of_scope_rows",
        )
    )
    official_count = int(official_payload.get("selected_count") or 0)
    historical_delisted_proven = (
        bool(official_payload)
        and not bool(official_payload.get("dry_run"))
        and official_count > 0
        and official_count == len(official_payload.get("records", []))
        and not official_missing_catalog
    )
    return {
        "scope": {
            "start": start,
            "end": end,
            "universe": "QMT 沪深北 A 股 + 沪深 ETF + 沪深指数",
            "historical_delisted_universe_proven": historical_delisted_proven,
            "historical_delisted_reason": (
                "SSE/SZSE official terminated lists seed historical symbols and lifecycles; "
                "all market and financial payloads remain sourced from local xtdata."
            ),
            "official_delisted_selected": official_count,
            "official_delisted_missing_catalog": official_missing_catalog,
        },
        "catalog": {
            "instruments": instruments,
            "daily_watermarks": daily_watermarks,
            "missing_active_daily_watermarks": missing_active_watermarks,
            "missing_scoped_daily_watermarks": missing_scoped_watermarks,
            "documented_upstream_unavailable_daily": documented_unavailable_daily,
            "documented_upstream_unavailable_daily_by_rule": (documented_unavailable_by_rule),
            "missing_financial_scope_checkpoints": missing_financial_checkpoints,
            "corporate_actions": actions,
        },
        "daily": {
            "database": daily_path.name,
            "integrity": daily_integrity,
            "primary_key": ["symbol", "ts"],
            "duplicate_keys_possible": False,
            "summary": daily_summary,
            "rows_by_source": daily_by_source,
            "clean": daily_clean,
        },
        "financial": {
            "databases": financial_years,
            "tables": dict(sorted(financial_tables.items())),
            "primary_key": [
                "symbol",
                "table_name",
                "report_date",
                "announcement_date",
                "row_ordinal",
            ],
            "duplicate_keys_possible": False,
            "point_in_time_field": "announcement_date",
            "clean": financial_clean,
        },
        "recent_jobs": recent_jobs,
        "accepted": (
            daily_clean
            and financial_clean
            and not missing_scoped_watermarks
            and missing_financial_checkpoints == 0
            and historical_delisted_proven
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit XtData 2010+ SQLite coverage")
    parser.add_argument("--root", type=Path, default=Path("data/sqlite"))
    parser.add_argument("--start", type=int, default=20100101)
    parser.add_argument("--end", type=int, default=20260717)
    parser.add_argument("--official-universe-report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = audit(
        args.root,
        start=args.start,
        end=args.end,
        official_universe_report=args.official_universe_report,
    )
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(encoded, encoding="utf-8")
        temporary.replace(args.output)
    print(encoded, end="")
    return 0 if payload["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
