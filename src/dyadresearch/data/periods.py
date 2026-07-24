from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from dyadresearch.data.aggregation import DERIVED_PERIODS, aggregate_bars, base_period
from dyadresearch.data.manifest import query_fingerprint
from dyadresearch.data.models import QueryResult
from dyadresearch.data.query import MarketDataReader


def query_period_bars(
    reader: MarketDataReader,
    symbols: Iterable[str],
    *,
    period: str,
    start: int,
    end: int,
    strict: bool = True,
) -> QueryResult:
    normalized = sorted({symbol.upper() for symbol in symbols})
    raw_period = base_period(period)
    result = reader.query_bars(
        normalized,
        period=raw_period,
        start=start,
        end=end,
        strict=strict,
    )
    if period not in DERIVED_PERIODS:
        return result
    bars = aggregate_bars(result.bars, period)
    fingerprint = query_fingerprint(
        paths=(Path(path) for path in result.paths),
        query={
            "symbols": normalized,
            "period": period,
            "base_period": raw_period,
            "start": start,
            "end": end,
        },
        bars=bars,
    )
    return QueryResult(
        bars=bars,
        paths=result.paths,
        warnings=result.warnings,
        fingerprint=fingerprint,
    )
