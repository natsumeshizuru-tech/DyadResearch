from decimal import Decimal

import pytest

from dyadresearch.backtest.fees import calculate_fees
from dyadresearch.backtest.models import Side
from dyadresearch.backtest.policy import BacktestPolicy, get_policy


def test_a_share_fees_apply_minimum_and_sell_stamp_duty() -> None:
    policy = BacktestPolicy()
    buy = calculate_fees(policy, Side.BUY, Decimal("10"), 100)
    sell = calculate_fees(policy, Side.SELL, Decimal("10"), 100)
    assert buy.commission == Decimal("5.0000")
    assert buy.stamp_duty == 0
    assert sell.stamp_duty == Decimal("0.5000")
    assert sell.total == Decimal("5.5000")

    large_sell = calculate_fees(policy, Side.SELL, Decimal("20"), 10_000)
    assert large_sell.commission == Decimal("20.0000")
    assert large_sell.stamp_duty == Decimal("100.0000")
    assert large_sell.total == Decimal("120.0000")


def test_policy_validation_and_named_policies() -> None:
    assert get_policy("qmt_compat").name == "qmt_compat"
    assert get_policy("legacy_compare").name == "legacy_compare"
    with pytest.raises(ValueError, match="unknown"):
        get_policy("invented")
    with pytest.raises(ValueError, match="at least one"):
        BacktestPolicy(execution_delay_bars=0)
    with pytest.raises(ValueError, match="participation"):
        BacktestPolicy(max_volume_participation=Decimal("0"))
