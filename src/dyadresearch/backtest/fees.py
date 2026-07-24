from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from dyadresearch.backtest.models import FeeBreakdown, Side
from dyadresearch.backtest.policy import BacktestPolicy

MONEY = Decimal("0.0001")


def calculate_fees(
    policy: BacktestPolicy, side: Side, price: Decimal, quantity: int
) -> FeeBreakdown:
    notional = price * quantity
    commission = max(policy.minimum_commission, notional * policy.commission_rate).quantize(
        MONEY, rounding=ROUND_HALF_UP
    )
    stamp = (notional * policy.stamp_duty_rate if side is Side.SELL else Decimal("0")).quantize(
        MONEY, rounding=ROUND_HALF_UP
    )
    transfer = (notional * policy.transfer_fee_rate).quantize(MONEY, rounding=ROUND_HALF_UP)
    return FeeBreakdown(commission, stamp, transfer)
