from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class BacktestPolicy:
    name: str = "strict_research"
    initial_cash: Decimal = Decimal("1000000")
    execution_delay_bars: int = 1
    enforce_t1: bool = True
    buy_lot_size: int = 100
    limit_ratio: Decimal = Decimal("0.10")
    commission_rate: Decimal = Decimal("0.0001")
    minimum_commission: Decimal = Decimal("5")
    stamp_duty_rate: Decimal = Decimal("0.0005")
    transfer_fee_rate: Decimal = Decimal("0")
    slippage_bps: Decimal = Decimal("0")
    max_volume_participation: Decimal = Decimal("1")
    allow_partial_fills: bool = True
    conservative_limit_board: bool = True
    apply_corporate_actions: bool = True
    random_seed: int = 0

    def __post_init__(self) -> None:
        if self.execution_delay_bars < 1:
            raise ValueError("execution_delay_bars must be at least one")
        if self.buy_lot_size <= 0:
            raise ValueError("buy_lot_size must be positive")
        if not Decimal("0") < self.max_volume_participation <= Decimal("1"):
            raise ValueError("max_volume_participation must be in (0, 1]")
        for value in (
            self.commission_rate,
            self.minimum_commission,
            self.stamp_duty_rate,
            self.transfer_fee_rate,
            self.slippage_bps,
        ):
            if value < 0:
                raise ValueError("cost and slippage settings cannot be negative")


def get_policy(name: str, **overrides: Any) -> BacktestPolicy:
    if name == "strict_research":
        base = BacktestPolicy()
    elif name == "qmt_compat":
        base = BacktestPolicy(name=name)
    elif name == "legacy_compare":
        base = BacktestPolicy(
            name=name,
            max_volume_participation=Decimal("1"),
            allow_partial_fills=True,
        )
    else:
        raise ValueError(f"unknown backtest policy: {name}")
    return replace(base, **overrides)
