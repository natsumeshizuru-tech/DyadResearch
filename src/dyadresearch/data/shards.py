from __future__ import annotations

from pathlib import Path

from dyadresearch.config import DataConfig


def symbol_market(symbol: str) -> str:
    parts = symbol.upper().rsplit(".", 1)
    if len(parts) != 2 or parts[1] not in {"SH", "SZ", "BJ"}:
        raise ValueError(f"unsupported symbol: {symbol}")
    return parts[1]


def months_between(start: int, end: int) -> tuple[str, ...]:
    year, month = divmod(start // 100, 100)
    end_year, end_month = divmod(end // 100, 100)
    values: list[str] = []
    while (year, month) <= (end_year, end_month):
        values.append(f"{year:04d}{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return tuple(values)


def bar_paths(
    config: DataConfig, symbols: list[str], period: str, start: int, end: int
) -> tuple[Path, ...]:
    if period == "1d":
        return (config.root / config.daily_bars,)
    if period != "1m":
        raise ValueError(f"unsupported raw period: {period}")
    markets = sorted({symbol_market(symbol) for symbol in symbols})
    return tuple(
        config.root / config.minute_pattern.format(market=market, year_month=year_month)
        for year_month in months_between(start, end)
        for market in markets
    )


def fundamental_paths(config: DataConfig, start_year: int, end_year: int) -> tuple[Path, ...]:
    return tuple(
        config.root / config.fundamentals_pattern.format(year=year)
        for year in range(start_year, end_year + 1)
    )
