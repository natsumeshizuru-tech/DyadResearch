from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from dyadresearch.data.models import Bar

CHINA_TZ = ZoneInfo("Asia/Shanghai")
MINUTE_SIZES = {"5m": 5, "15m": 15, "30m": 30, "1h": 60}
DAILY_PERIODS = {"1w", "1mon", "1q", "1hy", "1y"}
DERIVED_PERIODS = {*MINUTE_SIZES, *DAILY_PERIODS}


def base_period(target_period: str) -> str:
    if target_period in MINUTE_SIZES:
        return "1m"
    if target_period in DAILY_PERIODS:
        return "1d"
    if target_period in {"1m", "1d"}:
        return target_period
    raise ValueError(f"unsupported period: {target_period}")


def aggregate_bars(bars: tuple[Bar, ...], target_period: str) -> tuple[Bar, ...]:
    if target_period in DAILY_PERIODS:
        return _aggregate_daily_bars(bars, target_period)
    if target_period not in MINUTE_SIZES:
        raise ValueError(f"unsupported derived period: {target_period}")
    size = MINUTE_SIZES[target_period]
    groups: dict[tuple[str, int, str, int], list[Bar]] = defaultdict(list)
    for bar in bars:
        local = datetime.fromtimestamp(bar.ts / 1000, tz=CHINA_TZ)
        minute = local.hour * 60 + local.minute
        if 570 <= minute <= 690:
            session, elapsed = "am", max(1, minute - 570)
        elif 780 <= minute <= 900:
            session, elapsed = "pm", max(1, minute - 780)
        else:
            continue
        bucket = (elapsed - 1) // size
        groups[(bar.symbol, bar.trade_date, session, bucket)].append(bar)
    result = [_aggregate_group(group, target_period) for group in groups.values()]
    return tuple(sorted(result, key=lambda item: (item.ts, item.symbol)))


def _aggregate_daily_bars(bars: tuple[Bar, ...], target_period: str) -> tuple[Bar, ...]:
    groups: dict[tuple[str, int, int], list[Bar]] = defaultdict(list)
    for bar in bars:
        year = bar.trade_date // 10000
        month = (bar.trade_date // 100) % 100
        if target_period == "1w":
            local = datetime.strptime(str(bar.trade_date), "%Y%m%d")
            iso_year, iso_week, _ = local.isocalendar()
            key = (iso_year, iso_week)
        elif target_period == "1mon":
            key = (year, month)
        elif target_period == "1q":
            key = (year, (month - 1) // 3 + 1)
        elif target_period == "1hy":
            key = (year, 1 if month <= 6 else 2)
        else:
            key = (year, 1)
        groups[(bar.symbol, *key)].append(bar)
    result = [_aggregate_group(group, target_period) for group in groups.values()]
    return tuple(sorted(result, key=lambda item: (item.ts, item.symbol)))


def _aggregate_group(group: list[Bar], target_period: str) -> Bar:
    ordered = sorted(group, key=lambda item: item.ts)
    first, last = ordered[0], ordered[-1]
    highs = [item.high for item in ordered if item.high is not None]
    lows = [item.low for item in ordered if item.low is not None]
    amounts = [item.amount for item in ordered if item.amount is not None]
    return Bar(
        symbol=first.symbol,
        ts=last.ts,
        trade_date=first.trade_date,
        open=first.open,
        high=max(highs) if highs else None,
        low=min(lows) if lows else None,
        close=last.close,
        volume=sum(item.volume for item in ordered),
        amount=sum(amounts, Decimal("0")) if amounts else None,
        settlement_price=last.settlement_price,
        open_interest=last.open_interest,
        pre_close=first.pre_close,
        suspend_flag=max(item.suspend_flag for item in ordered),
        source=f"{last.source}:derived_{target_period}",
        ingested_at=max(item.ingested_at for item in ordered),
        source_hash=last.source_hash,
    )
