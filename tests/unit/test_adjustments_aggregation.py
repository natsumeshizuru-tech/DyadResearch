from dataclasses import replace
from decimal import Decimal

import pytest

from dyadresearch.data.adjustments import adjust_bars
from dyadresearch.data.aggregation import aggregate_bars
from dyadresearch.data.models import Bar, CorporateAction


def make_bar(ts: int, close: str, *, volume: int = 100) -> Bar:
    price = Decimal(close)
    return Bar(
        symbol="000001.SZ",
        ts=ts,
        trade_date=20250711,
        open=price,
        high=price,
        low=price,
        close=price,
        volume=volume,
        amount=price * volume,
        pre_close=price,
    )


def test_front_and_back_adjustment_are_inverse_for_one_event() -> None:
    bar = make_bar(1, "10")
    action = CorporateAction(
        "000001.SZ",
        20250712,
        Decimal("0.1"),
        Decimal("0.1"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0.9"),
    )
    front = adjust_bars((bar,), (action,), mode="front")[0]
    assert front.close == Decimal("9")
    back_event = replace(action, action_date=20250711)
    restored = adjust_bars((front,), (back_event,), mode="back")[0]
    assert restored.close == Decimal("10")


def test_ratio_adjustment_matches_xtdata_anchor_semantics() -> None:
    action = CorporateAction(
        "000001.SZ",
        20250712,
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("2"),
    )
    front = adjust_bars((make_bar(1, "10"),), (action,), mode="front_ratio")[0]
    back_event = replace(action, action_date=20250711)
    back = adjust_bars((make_bar(1, "10"),), (back_event,), mode="back_ratio")[0]

    assert front.close == Decimal("5")
    assert back.close == Decimal("20")


def test_ratio_adjustment_rejects_nonpositive_dr() -> None:
    action = CorporateAction(
        "000001.SZ",
        20250711,
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
    )
    with pytest.raises(ValueError, match="must be positive"):
        adjust_bars((make_bar(1, "10"),), (action,), mode="back_ratio")


def test_minute_aggregation_does_not_mix_lunch_sessions() -> None:
    minute = 60_000
    # UTC epochs map to 09:31, 09:32 and 13:01 Asia/Shanghai on 2025-07-11.
    bars = (
        make_bar(1752197460000, "10", volume=10),
        make_bar(1752197520000, "11", volume=20),
        make_bar(1752210060000, "12", volume=30),
    )
    del minute
    result = aggregate_bars(bars, "5m")
    assert len(result) == 2
    assert result[0].open == Decimal("10")
    assert result[0].close == Decimal("11")
    assert result[0].volume == 30
    assert result[1].close == Decimal("12")


def test_aggregation_rejects_unknown_period() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        aggregate_bars((), "2m")


def test_daily_aggregation_builds_quarter_and_year_without_manufacturing_prices() -> None:
    bars = tuple(
        replace(
            make_bar(index, close, volume=index * 10),
            trade_date=trade_date,
            open=Decimal(open_),
            high=Decimal(high),
            low=Decimal(low),
        )
        for index, (trade_date, open_, high, low, close) in enumerate(
            (
                (20240102, "10", "12", "9", "11"),
                (20240329, "11", "13", "10", "12"),
                (20240401, "12", "14", "11", "13"),
            ),
            start=1,
        )
    )

    quarters = aggregate_bars(bars, "1q")
    yearly = aggregate_bars(bars, "1y")

    assert len(quarters) == 2
    assert quarters[0].open == Decimal("10")
    assert quarters[0].close == Decimal("12")
    assert quarters[0].high == Decimal("13")
    assert quarters[0].volume == 30
    assert quarters[0].source.endswith("derived_1q")
    assert len(yearly) == 1
    assert yearly[0].close == Decimal("13")
    assert yearly[0].volume == 60
