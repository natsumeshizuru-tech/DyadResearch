from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(StrEnum):
    REJECTED = "rejected"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"


ACTIVE_ORDER_STATUSES = {OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED}


@dataclass(slots=True)
class Order:
    order_id: int
    symbol: str
    side: Side
    quantity: int
    order_type: OrderType
    limit_price: Decimal | None
    submitted_ts: int
    eligible_sequence: int
    status: OrderStatus = OrderStatus.SUBMITTED
    reject_reason: str | None = None
    filled_quantity: int = 0
    average_fill_price: Decimal = Decimal("0")
    frozen_cash: Decimal = Decimal("0")
    frozen_quantity: int = 0

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.filled_quantity


@dataclass(frozen=True, slots=True)
class FeeBreakdown:
    commission: Decimal
    stamp_duty: Decimal
    transfer_fee: Decimal

    @property
    def total(self) -> Decimal:
        return self.commission + self.stamp_duty + self.transfer_fee


@dataclass(frozen=True, slots=True)
class Trade:
    trade_id: int
    order_id: int
    symbol: str
    side: Side
    quantity: int
    price: Decimal
    ts: int
    fees: FeeBreakdown

    @property
    def notional(self) -> Decimal:
        return self.price * self.quantity


@dataclass(slots=True)
class Position:
    symbol: str
    quantity: int = 0
    available_quantity: int = 0
    today_bought: int = 0
    frozen_quantity: int = 0
    average_cost: Decimal = Decimal("0")
    last_price: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class EquityPoint:
    ts: int
    cash: Decimal
    frozen_cash: Decimal
    position_value: Decimal
    total_assets: Decimal
    net_value: Decimal
    drawdown: Decimal


@dataclass(frozen=True, slots=True)
class BacktestResult:
    run_id: str
    result_hash: str
    data_fingerprint: str
    policy: dict[str, Any]
    bars_processed: int
    orders: tuple[Order, ...]
    trades: tuple[Trade, ...]
    equity: tuple[EquityPoint, ...]
    final_positions: dict[str, int]
    metrics: dict[str, float]
    event_log: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
