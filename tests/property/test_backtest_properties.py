from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from dyadresearch.backtest.engine import BacktestEngine
from dyadresearch.backtest.policy import BacktestPolicy
from dyadresearch.data.models import Bar
from dyadresearch.strategy.examples import BuyAndHoldStrategy


@given(st.lists(st.integers(min_value=5, max_value=100), min_size=2, max_size=25))
@settings(max_examples=30, deadline=None)
def test_random_price_paths_preserve_nonnegative_ledger(prices: list[int]) -> None:
    bars = tuple(
        Bar(
            "000001.SZ",
            index,
            20250101 + index,
            Decimal(price),
            Decimal(price),
            Decimal(price),
            Decimal(price),
            1000,
            Decimal(price * 1000),
            pre_close=Decimal(price),
        )
        for index, price in enumerate(prices, start=1)
    )
    policy = BacktestPolicy(initial_cash=Decimal("100000"))
    result = BacktestEngine().run(
        BuyAndHoldStrategy("000001.SZ"),
        bars=bars,
        data_fingerprint="property",
        policy=policy,
    )
    assert all(point.cash >= 0 and point.total_assets >= 0 for point in result.equity)
    assert all(point.frozen_cash >= 0 for point in result.equity)
    repeat = BacktestEngine().run(
        BuyAndHoldStrategy("000001.SZ"),
        bars=bars,
        data_fingerprint="property",
        policy=policy,
    )
    assert result.result_hash == repeat.result_hash
