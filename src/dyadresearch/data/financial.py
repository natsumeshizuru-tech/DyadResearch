from __future__ import annotations

import json

from dyadresearch.config import DataConfig
from dyadresearch.data.models import FinancialRecord
from dyadresearch.data.shards import fundamental_paths
from dyadresearch.data.sqlite import readonly_connection, require_columns

FINANCIAL_COLUMNS = {
    "symbol",
    "table_name",
    "report_date",
    "announcement_date",
    "row_ordinal",
    "raw_json",
    "source",
    "ingested_at",
    "source_hash",
}


class FinancialReader:
    def __init__(self, config: DataConfig) -> None:
        self.config = config

    def as_of(
        self,
        symbols: list[str],
        *,
        table_names: list[str],
        as_of_date: int,
        earliest_report_date: int = 19900101,
    ) -> tuple[FinancialRecord, ...]:
        normalized_symbols = sorted({symbol.upper() for symbol in symbols})
        normalized_tables = sorted(set(table_names))
        if not normalized_symbols or not normalized_tables:
            return ()
        paths = fundamental_paths(self.config, earliest_report_date // 10_000, as_of_date // 10_000)
        versions: dict[tuple[str, str, int, int], list[FinancialRecord]] = {}
        symbol_marks = ",".join("?" for _ in normalized_symbols)
        table_marks = ",".join("?" for _ in normalized_tables)
        for path in paths:
            if not path.is_file():
                continue
            with readonly_connection(path, busy_timeout_ms=self.config.busy_timeout_ms) as con:
                require_columns(con, "financial_records", FINANCIAL_COLUMNS)
                sql = (
                    "SELECT symbol, table_name, report_date, announcement_date, row_ordinal, "
                    "raw_json, source_hash FROM financial_records "
                    f"WHERE symbol IN ({symbol_marks}) AND table_name IN ({table_marks}) "
                    "AND report_date >= ? AND announcement_date > 0 AND announcement_date <= ? "
                    "ORDER BY symbol, table_name, report_date, announcement_date, row_ordinal"
                )
                params = [*normalized_symbols, *normalized_tables, earliest_report_date, as_of_date]
                for row in con.execute(sql, params):
                    record = FinancialRecord(
                        symbol=str(row[0]),
                        table_name=str(row[1]),
                        report_date=int(row[2]),
                        announcement_date=int(row[3]),
                        row_ordinal=int(row[4]),
                        values=json.loads(str(row[5])),
                        source_hash=str(row[6]),
                    )
                    version_key = (
                        record.symbol,
                        record.table_name,
                        record.report_date,
                        record.announcement_date,
                    )
                    versions.setdefault(version_key, []).append(record)
        latest_announcements: dict[tuple[str, str, int], int] = {}
        for symbol, table_name, report_date, announcement_date in versions:
            report_key = (symbol, table_name, report_date)
            latest_announcements[report_key] = max(
                announcement_date,
                latest_announcements.get(report_key, 0),
            )
        selected = [
            record
            for (symbol, table_name, report_date, announcement_date), records in versions.items()
            if latest_announcements[(symbol, table_name, report_date)] == announcement_date
            for record in records
        ]
        return tuple(
            sorted(
                selected,
                key=lambda item: (item.symbol, item.table_name, item.report_date, item.row_ordinal),
            )
        )
