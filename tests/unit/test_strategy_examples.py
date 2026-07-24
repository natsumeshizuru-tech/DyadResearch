from decimal import Decimal

import pytest

from dyadresearch.backtest.engine import BacktestEngine
from dyadresearch.backtest.policy import BacktestPolicy
from dyadresearch.data.models import Bar
from dyadresearch.strategy.examples import (
    BuyAndHoldStrategy,
    FullMarketLowVolumeRatioMomentumStrategy,
    LowVolumeRatioMomentumStrategy,
    MovingAverageCrossStrategy,
)
from dyadresearch.strategy.universe import MarketSignal


def price_bars(values: list[int]) -> tuple[Bar, ...]:
    return tuple(
        Bar(
            symbol="000001.SZ",
            ts=index,
            trade_date=20250100 + index,
            open=Decimal(value),
            high=Decimal(value),
            low=Decimal(value),
            close=Decimal(value),
            volume=1000,
            amount=Decimal(value * 1000),
            pre_close=Decimal(value),
        )
        for index, value in enumerate(values, start=1)
    )


def test_buy_and_hold_runs_on_unified_kernel() -> None:
    result = BacktestEngine().run(
        BuyAndHoldStrategy("000001.SZ"),
        bars=price_bars([10, 11, 12]),
        data_fingerprint="fixed",
        policy=BacktestPolicy(initial_cash=Decimal("10000")),
    )
    assert len(result.trades) == 1
    assert result.trades[0].ts == 2
    assert result.trades[0].quantity == 900
    assert result.trades[0].notional + result.trades[0].fees.total <= Decimal("10000")
    assert result.final_positions == {"000001.SZ": 900}


def test_moving_average_parameters_are_validated() -> None:
    with pytest.raises(ValueError, match="fast < slow"):
        MovingAverageCrossStrategy("000001.SZ", fast=5, slow=5)


def test_low_volume_ratio_momentum_buys_twenty_percent_and_sells_next_open() -> None:
    symbol = "603580.SH"
    days = [20260708, 20260709, 20260710, 20260713, 20260714, 20260716, 20260717]
    bars: list[Bar] = []
    ts = 0
    first_ts_by_date: dict[int, int] = {}
    for trade_date in days:
        for minute in range(240):
            ts += 1
            first_ts_by_date.setdefault(trade_date, ts)
            if trade_date == 20260716:
                price = Decimal("10.80")
                volume = 100 if minute == 0 else 100_000
                previous_close = Decimal("10")
            elif trade_date == 20260717:
                price = Decimal("11.00")
                volume = 100_000
                previous_close = Decimal("10.80")
            else:
                price = Decimal("10")
                volume = 100_000
                previous_close = Decimal("10")
            bars.append(
                Bar(
                    symbol=symbol,
                    ts=ts,
                    trade_date=trade_date,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=volume,
                    amount=price * volume,
                    pre_close=previous_close,
                )
            )
    strategy = LowVolumeRatioMomentumStrategy(
        symbol,
        capital_schedule=((20260101, Decimal("1000000000")),),
        previous_closes={20260716: Decimal("10"), 20260717: Decimal("10.80")},
    )

    result = BacktestEngine().run(
        strategy,
        bars=tuple(bars),
        data_fingerprint="minute-fixed",
        policy=BacktestPolicy(initial_cash=Decimal("100000")),
    )

    buy = next(trade for trade in result.trades if trade.side.value == "buy")
    sell = next(trade for trade in result.trades if trade.side.value == "sell")
    assert buy.ts > first_ts_by_date[20260716]
    assert buy.quantity == 1800
    assert buy.notional + buy.fees.total <= Decimal("20000")
    assert sell.ts == first_ts_by_date[20260717]
    assert sell.price == Decimal("11.00")
    assert result.final_positions == {}


def test_full_market_strategy_selects_best_signal_and_exits_next_open() -> None:
    signals = (
        MarketSignal(
            symbol="000001.SZ",
            trade_date=20260716,
            ts=1,
            price_gain=Decimal("0.08"),
            volume_ratio=Decimal("0.50"),
            market_cap=Decimal("10000000000"),
            average_daily_volume=Decimal("1000000"),
            limit_ratio=Decimal("0.10"),
            previous_close=Decimal("10"),
        ),
        MarketSignal(
            symbol="600000.SH",
            trade_date=20260716,
            ts=1,
            price_gain=Decimal("0.09"),
            volume_ratio=Decimal("0.55"),
            market_cap=Decimal("20000000000"),
            average_daily_volume=Decimal("1000000"),
            limit_ratio=Decimal("0.10"),
            previous_close=Decimal("37.13"),
        ),
    )

    def bar(symbol: str, ts: int, trade_date: int, price: str, pre_close: str = "10") -> Bar:
        value = Decimal(price)
        return Bar(
            symbol=symbol,
            ts=ts,
            trade_date=trade_date,
            open=value,
            high=value,
            low=value,
            close=value,
            volume=1_000_000,
            amount=value * 1_000_000,
            pre_close=Decimal(pre_close),
        )

    result = BacktestEngine().run(
        FullMarketLowVolumeRatioMomentumStrategy(signals),
        bars=(
            bar("000001.SZ", 1, 20260716, "10.8"),
            bar("600000.SH", 1, 20260716, "40.80", "37.13"),
            bar("000001.SZ", 2, 20260716, "10.85"),
            bar("600000.SH", 2, 20260716, "40.84", "37.13"),
            bar("000001.SZ", 3, 20260717, "11.20", "10.85"),
        ),
        data_fingerprint="full-market-fixed",
        policy=BacktestPolicy(initial_cash=Decimal("100000")),
    )

    assert [(trade.symbol, trade.side.value) for trade in result.trades] == [
        ("000001.SZ", "buy"),
        ("000001.SZ", "sell"),
    ]
    assert result.trades[-1].price == Decimal("11.20")
    assert result.final_positions == {}
    skipped = next(
        event
        for event in result.event_log
        if event.get("reason") == "next_minute_open_at_upper_limit"
    )
    assert skipped["symbol"] == "600000.SH"
    assert skipped["opening_price"] == 40.84


def test_full_market_strategy_holds_at_most_five_twenty_percent_positions() -> None:
    symbols = ("000001.SZ", "000002.SZ", "000003.SZ", "600000.SH", "600001.SH", "600002.SH")
    signals = tuple(
        MarketSignal(
            symbol=symbol,
            trade_date=20260716,
            ts=1,
            price_gain=Decimal("0.08") + Decimal(index) / Decimal("1000"),
            volume_ratio=Decimal("0.50"),
            market_cap=Decimal("10000000000"),
            average_daily_volume=Decimal("1000000"),
            limit_ratio=Decimal("0.10"),
            previous_close=Decimal("10"),
        )
        for index, symbol in enumerate(symbols)
    )

    def bar(symbol: str, ts: int, price: str) -> Bar:
        value = Decimal(price)
        return Bar(
            symbol=symbol,
            ts=ts,
            trade_date=20260716,
            open=value,
            high=value,
            low=value,
            close=value,
            volume=1_000_000,
            amount=value * 1_000_000,
            pre_close=Decimal("10"),
        )

    bars = tuple(
        bar(symbol, ts, price) for ts, price in ((1, "10.8"), (2, "10.85")) for symbol in symbols
    )
    result = BacktestEngine().run(
        FullMarketLowVolumeRatioMomentumStrategy(signals),
        bars=bars,
        data_fingerprint="five-position-fixed",
        policy=BacktestPolicy(initial_cash=Decimal("100000")),
    )

    assert len(result.trades) == 5
    assert len(result.final_positions) == 5
    assert all(trade.side.value == "buy" for trade in result.trades)
    assert all(trade.notional + trade.fees.total <= Decimal("20000") for trade in result.trades)
    assert sum(event.get("reason") == "portfolio_position_limit" for event in result.event_log) == 1


def test_full_market_entry_only_has_one_next_minute_chance() -> None:
    signal = MarketSignal(
        symbol="000001.SZ",
        trade_date=20260716,
        ts=1,
        price_gain=Decimal("0.08"),
        volume_ratio=Decimal("0.50"),
        market_cap=Decimal("10000000000"),
        average_daily_volume=Decimal("1000000"),
        limit_ratio=Decimal("0.10"),
        previous_close=Decimal("10"),
    )

    def bar(ts: int, price: str, volume: int) -> Bar:
        value = Decimal(price)
        return Bar(
            symbol=signal.symbol,
            ts=ts,
            trade_date=signal.trade_date,
            open=value,
            high=value,
            low=value,
            close=value,
            volume=volume,
            amount=value * volume,
            pre_close=None,
        )

    result = BacktestEngine().run(
        FullMarketLowVolumeRatioMomentumStrategy((signal,)),
        bars=(bar(1, "10.8", 1_000_000), bar(2, "10.85", 0), bar(3, "10.70", 1_000_000)),
        data_fingerprint="one-next-minute-chance",
        policy=BacktestPolicy(initial_cash=Decimal("100000")),
    )

    assert result.trades == ()
    skipped = next(
        event for event in result.event_log if event.get("reason") == "next_minute_open_unavailable"
    )
    assert skipped["symbol"] == signal.symbol
