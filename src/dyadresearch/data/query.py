from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from decimal import Decimal

from dyadresearch.config import DataConfig
from dyadresearch.data.capabilities import require_bar_capability
from dyadresearch.data.manifest import query_fingerprint
from dyadresearch.data.models import Bar, DataWarning, QueryResult
from dyadresearch.data.shards import bar_paths
from dyadresearch.data.sqlite import readonly_connection, require_columns

BAR_COLUMNS = (
    "symbol",
    "ts",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "settlement_price",
    "open_interest",
    "pre_close",
    "suspend_flag",
    "source",
    "ingested_at",
    "source_hash",
)


class MarketDataReader:
    def __init__(self, config: DataConfig) -> None:
        self.config = config

    def query_bars(
        self,
        symbols: Iterable[str],
        *,
        period: str,
        start: int,
        end: int,
        strict: bool = True,
    ) -> QueryResult:
        normalized = sorted({symbol.upper() for symbol in symbols})
        if not normalized:
            return QueryResult((), (), (), query_fingerprint(paths=(), query={}, bars=()))
        warnings: list[DataWarning] = []
        if strict:
            require_bar_capability(period, normalized, start, end, data_root=self.config.root)
        else:
            try:
                require_bar_capability(period, normalized, start, end, data_root=self.config.root)
            except Exception as exc:
                warnings.append(DataWarning("RANGE_OUTSIDE_CAPABILITY", str(exc)))
        selected_paths = bar_paths(self.config, normalized, period, start, end)
        existing_paths = tuple(path for path in selected_paths if path.is_file())
        missing = [str(path) for path in selected_paths if not path.is_file()]
        if missing:
            message = f"missing {len(missing)} expected shard(s)"
            if strict:
                raise FileNotFoundError(f"{message}: {missing[0]}")
            warnings.append(DataWarning("MISSING_SHARDS", message))
        rows: dict[tuple[str, int], Bar] = {}
        for path in existing_paths:
            with readonly_connection(
                path,
                busy_timeout_ms=self.config.busy_timeout_ms,
                immutable=self.config.immutable,
            ) as connection:
                require_columns(connection, "bars", set(BAR_COLUMNS))
                for offset in range(0, len(normalized), 900):
                    batch = normalized[offset : offset + 900]
                    placeholders = ",".join("?" for _ in batch)
                    sql = (
                        f"SELECT {','.join(BAR_COLUMNS)} FROM bars "
                        f"WHERE symbol IN ({placeholders}) AND trade_date BETWEEN ? AND ? "
                        "ORDER BY ts, symbol"
                    )
                    for row in connection.execute(sql, [*batch, start, end]):
                        bar = bar_from_row(row)
                        rows[(bar.symbol, bar.ts)] = bar
        bars = tuple(sorted(rows.values(), key=lambda item: (item.ts, item.symbol)))
        query = {"symbols": normalized, "period": period, "start": start, "end": end}
        fingerprint = query_fingerprint(paths=existing_paths, query=query, bars=bars)
        return QueryResult(
            bars=bars,
            paths=tuple(str(path.resolve()) for path in existing_paths),
            warnings=tuple(warnings),
            fingerprint=fingerprint,
        )


def _decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def bar_from_row(row: sqlite3.Row) -> Bar:
    values = dict(row)
    return Bar(
        symbol=str(values["symbol"]),
        ts=int(values["ts"]),
        trade_date=int(values["trade_date"]),
        open=_decimal(values["open"]),
        high=_decimal(values["high"]),
        low=_decimal(values["low"]),
        close=_decimal(values["close"]),
        volume=int(values["volume"] or 0),
        amount=_decimal(values["amount"]),
        settlement_price=_decimal(values["settlement_price"]),
        open_interest=_decimal(values["open_interest"]),
        pre_close=_decimal(values["pre_close"]),
        suspend_flag=int(values["suspend_flag"] or 0),
        source=str(values["source"]),
        ingested_at=int(values["ingested_at"]),
        source_hash=None if values["source_hash"] is None else str(values["source_hash"]),
    )
