from __future__ import annotations

import hashlib
import json
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from dyadresearch.config import DataConfig
from dyadresearch.data.manifest import query_fingerprint
from dyadresearch.data.models import Bar
from dyadresearch.data.query import BAR_COLUMNS, bar_from_row
from dyadresearch.data.shards import symbol_market
from dyadresearch.data.sqlite import readonly_connection, require_columns
from dyadresearch.strategy.inputs import load_capital_schedules


@dataclass(frozen=True, slots=True)
class MarketSignal:
    symbol: str
    trade_date: int
    ts: int
    price_gain: Decimal
    volume_ratio: Decimal
    market_cap: Decimal
    average_daily_volume: Decimal
    limit_ratio: Decimal
    previous_close: Decimal


@dataclass(frozen=True, slots=True)
class FullMarketQueryResult:
    bars: tuple[Bar, ...]
    signals: tuple[MarketSignal, ...]
    symbols: tuple[str, ...]
    candidate_days: int
    scanned_minute_bars: int
    paths: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class _DailyCandidate:
    symbol: str
    trade_date: int
    previous_close: Decimal
    average_daily_volume: Decimal
    shares: Decimal
    limit_ratio: Decimal


def build_low_volume_full_market_data(
    config: DataConfig,
    *,
    start: int,
    end: int,
    market_cap_max: Decimal = Decimal("30000000000"),
    rise_threshold: Decimal = Decimal("0.07"),
    volume_ratio_max: Decimal = Decimal("0.6"),
    volume_lookback_days: int = 5,
    expected_minutes_per_day: int = 240,
) -> FullMarketQueryResult:
    if start > end:
        raise ValueError("full-market backtest start must not exceed end")
    if volume_lookback_days < 1:
        raise ValueError("volume_lookback_days must be positive")
    limit_ratios = main_board_limit_ratios(config, start=start, end=end)
    symbols = set(limit_ratios)
    if not symbols:
        raise ValueError("no Shanghai/Shenzhen main-board stocks are available")
    capital = load_capital_schedules(config, symbols, end=end)
    candidates, trading_dates = _daily_candidates(
        config,
        symbols=symbols,
        capital=capital,
        limit_ratios=limit_ratios,
        start=start,
        end=end,
        market_cap_max=market_cap_max,
        rise_threshold=rise_threshold,
        volume_lookback_days=volume_lookback_days,
    )
    next_dates = {
        trading_dates[index]: trading_dates[index + 1] for index in range(len(trading_dates) - 1)
    }
    bars_by_key: dict[tuple[str, int], Bar] = {}
    signals: list[MarketSignal] = []
    scanned_minute_bars = 0
    used_paths: set[Path] = set()
    for path, grouped in _group_pairs_by_path(config, candidates).items():
        if not path.is_file():
            continue
        used_paths.add(path)
        with readonly_connection(
            path, busy_timeout_ms=config.busy_timeout_ms, immutable=config.immutable
        ) as connection:
            require_columns(connection, "bars", set(BAR_COLUMNS))
            for symbol, dates in grouped.items():
                placeholders = ",".join("?" for _ in dates)
                rows = connection.execute(
                    f"SELECT {','.join(BAR_COLUMNS)} FROM bars WHERE symbol=? "
                    f"AND trade_date IN ({placeholders}) ORDER BY trade_date, ts",
                    [symbol, *dates],
                )
                by_date: dict[int, list[Bar]] = defaultdict(list)
                for row in rows:
                    bar = bar_from_row(row)
                    by_date[bar.trade_date].append(bar)
                    scanned_minute_bars += 1
                for trade_date, day_bars in by_date.items():
                    candidate = candidates[(symbol, trade_date)]
                    match = _first_signal(
                        day_bars,
                        candidate,
                        market_cap_max=market_cap_max,
                        rise_threshold=rise_threshold,
                        volume_ratio_max=volume_ratio_max,
                        expected_minutes_per_day=expected_minutes_per_day,
                    )
                    if match is None:
                        continue
                    index, signal = match
                    if index + 1 >= len(day_bars):
                        continue
                    signals.append(signal)
                    for bar in (day_bars[index], day_bars[index + 1]):
                        bars_by_key[(bar.symbol, bar.ts)] = bar
    exit_pairs = {
        (signal.symbol, next_dates[signal.trade_date])
        for signal in signals
        if signal.trade_date in next_dates and next_dates[signal.trade_date] <= end
    }
    for path, grouped in _group_symbol_dates(config, exit_pairs).items():
        if not path.is_file():
            continue
        used_paths.add(path)
        with readonly_connection(
            path, busy_timeout_ms=config.busy_timeout_ms, immutable=config.immutable
        ) as connection:
            require_columns(connection, "bars", set(BAR_COLUMNS))
            for symbol, dates in grouped.items():
                placeholders = ",".join("?" for _ in dates)
                rows = connection.execute(
                    f"SELECT {','.join(BAR_COLUMNS)} FROM bars WHERE symbol=? "
                    f"AND trade_date IN ({placeholders}) ORDER BY trade_date, ts",
                    [symbol, *dates],
                )
                seen_dates: set[int] = set()
                for row in rows:
                    bar = bar_from_row(row)
                    if bar.trade_date in seen_dates:
                        continue
                    seen_dates.add(bar.trade_date)
                    bars_by_key[(bar.symbol, bar.ts)] = bar
    bars = tuple(sorted(bars_by_key.values(), key=lambda item: (item.ts, item.symbol)))
    normalized_signals = tuple(sorted(signals, key=lambda item: (item.ts, item.symbol)))
    signal_symbols = tuple(sorted({item.symbol for item in normalized_signals}))
    resolved_paths = tuple(str(path.resolve()) for path in sorted(used_paths))
    query = {
        "strategy": "low_volume_ratio_momentum",
        "universe": "sh_sz_main_board",
        "start": start,
        "end": end,
        "market_cap_max": str(market_cap_max),
        "rise_threshold": str(rise_threshold),
        "volume_ratio_max": str(volume_ratio_max),
        "volume_lookback_days": volume_lookback_days,
        "candidate_days": len(candidates),
        "scanned_minute_bars": scanned_minute_bars,
        "signal_digest": hashlib.sha256(
            json.dumps(
                [
                    (
                        item.symbol,
                        item.trade_date,
                        item.ts,
                        str(item.volume_ratio),
                        str(item.limit_ratio),
                        str(item.previous_close),
                    )
                    for item in normalized_signals
                ],
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
    }
    fingerprint = query_fingerprint(paths=tuple(sorted(used_paths)), query=query, bars=bars)
    return FullMarketQueryResult(
        bars=bars,
        signals=normalized_signals,
        symbols=signal_symbols,
        candidate_days=len(candidates),
        scanned_minute_bars=scanned_minute_bars,
        paths=resolved_paths,
        fingerprint=fingerprint,
    )


def main_board_limit_ratios(config: DataConfig, *, start: int, end: int) -> dict[str, Decimal]:
    path = config.root / config.catalog
    with readonly_connection(path, busy_timeout_ms=config.busy_timeout_ms) as connection:
        rows = connection.execute(
            "SELECT symbol, name FROM instruments WHERE instrument_type='stock' "
            "AND (list_date IS NULL OR list_date<=?) AND (delist_date IS NULL OR delist_date>=?)",
            (end, start),
        ).fetchall()
    return {
        str(row[0]): Decimal("0.05") if "ST" in str(row[1] or "").upper() else Decimal("0.10")
        for row in rows
        if _is_main_board_symbol(str(row[0]))
    }


def _is_main_board_symbol(symbol: str) -> bool:
    code, _, market = symbol.upper().partition(".")
    if market == "SH":
        return code.startswith(("600", "601", "603", "605"))
    if market == "SZ":
        return code.startswith(("000", "001", "002", "003"))
    return False


def _daily_candidates(
    config: DataConfig,
    *,
    symbols: set[str],
    capital: dict[str, tuple[tuple[int, Decimal], ...]],
    limit_ratios: dict[str, Decimal],
    start: int,
    end: int,
    market_cap_max: Decimal,
    rise_threshold: Decimal,
    volume_lookback_days: int,
) -> tuple[dict[tuple[str, int], _DailyCandidate], tuple[int, ...]]:
    path = config.root / config.daily_bars
    prefix_filter = (
        "(symbol GLOB '600*.SH' OR symbol GLOB '601*.SH' OR symbol GLOB '603*.SH' "
        "OR symbol GLOB '605*.SH' OR symbol GLOB '000*.SZ' OR symbol GLOB '001*.SZ' "
        "OR symbol GLOB '002*.SZ' OR symbol GLOB '003*.SZ')"
    )
    sql = f"""
        WITH history AS (
            SELECT symbol, trade_date, high,
                   LAG(close) OVER (PARTITION BY symbol ORDER BY trade_date) AS previous_close,
                   AVG(volume) OVER (
                       PARTITION BY symbol ORDER BY trade_date
                       ROWS BETWEEN {volume_lookback_days} PRECEDING AND 1 PRECEDING
                   ) AS average_volume,
                   COUNT(volume) OVER (
                       PARTITION BY symbol ORDER BY trade_date
                       ROWS BETWEEN {volume_lookback_days} PRECEDING AND 1 PRECEDING
                   ) AS volume_days
            FROM bars
            WHERE trade_date<=? AND {prefix_filter}
        )
        SELECT symbol, trade_date, previous_close, average_volume
        FROM history
        WHERE trade_date BETWEEN ? AND ? AND volume_days=?
          AND previous_close>0 AND average_volume>0
          AND high>previous_close*(1+?)
        ORDER BY trade_date, symbol
    """
    candidates: dict[tuple[str, int], _DailyCandidate] = {}
    with readonly_connection(path, busy_timeout_ms=config.busy_timeout_ms) as connection:
        trading_dates = tuple(
            int(row[0])
            for row in connection.execute(
                "SELECT DISTINCT trade_date FROM bars WHERE trade_date BETWEEN ? AND ? "
                "ORDER BY trade_date",
                (start, end),
            )
        )
        rows = connection.execute(
            sql,
            (end, start, end, volume_lookback_days, float(rise_threshold)),
        )
        for row in rows:
            symbol = str(row[0])
            if symbol not in symbols:
                continue
            trade_date = int(row[1])
            shares = _shares_as_of(capital.get(symbol, ()), trade_date)
            if shares is None:
                continue
            previous_close = Decimal(str(row[2]))
            if previous_close * (Decimal("1") + rise_threshold) * shares >= market_cap_max:
                continue
            candidates[(symbol, trade_date)] = _DailyCandidate(
                symbol=symbol,
                trade_date=trade_date,
                previous_close=previous_close,
                average_daily_volume=Decimal(str(row[3])),
                shares=shares,
                limit_ratio=limit_ratios[symbol],
            )
    return candidates, trading_dates


def _shares_as_of(schedule: tuple[tuple[int, Decimal], ...], trade_date: int) -> Decimal | None:
    keys = [item[0] for item in schedule]
    index = bisect_right(keys, trade_date) - 1
    return None if index < 0 else schedule[index][1]


def _first_signal(
    bars: list[Bar],
    candidate: _DailyCandidate,
    *,
    market_cap_max: Decimal,
    rise_threshold: Decimal,
    volume_ratio_max: Decimal,
    expected_minutes_per_day: int,
) -> tuple[int, MarketSignal] | None:
    cumulative_volume = 0
    for index, bar in enumerate(bars):
        cumulative_volume += max(0, bar.volume)
        if bar.close is None:
            continue
        elapsed = Decimal(min(index + 1, expected_minutes_per_day))
        expected_volume = candidate.average_daily_volume * elapsed / expected_minutes_per_day
        if expected_volume <= 0:
            continue
        price_gain = bar.close / candidate.previous_close - Decimal("1")
        volume_ratio = Decimal(cumulative_volume) / expected_volume
        market_cap = bar.close * candidate.shares
        if (
            price_gain > rise_threshold
            and volume_ratio < volume_ratio_max
            and market_cap < market_cap_max
        ):
            return index, MarketSignal(
                symbol=bar.symbol,
                trade_date=bar.trade_date,
                ts=bar.ts,
                price_gain=price_gain,
                volume_ratio=volume_ratio,
                market_cap=market_cap,
                average_daily_volume=candidate.average_daily_volume,
                limit_ratio=candidate.limit_ratio,
                previous_close=candidate.previous_close,
            )
    return None


def _group_pairs_by_path(
    config: DataConfig, candidates: dict[tuple[str, int], _DailyCandidate]
) -> dict[Path, dict[str, list[int]]]:
    return _group_symbol_dates(config, set(candidates))


def _group_symbol_dates(
    config: DataConfig, pairs: set[tuple[str, int]]
) -> dict[Path, dict[str, list[int]]]:
    grouped: dict[Path, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for symbol, trade_date in pairs:
        path = config.root / config.minute_pattern.format(
            market=symbol_market(symbol), year_month=str(trade_date)[:6]
        )
        grouped[path][symbol].add(trade_date)
    return {
        path: {symbol: sorted(dates) for symbol, dates in values.items()}
        for path, values in grouped.items()
    }
