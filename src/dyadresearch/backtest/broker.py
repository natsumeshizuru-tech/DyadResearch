from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from dyadresearch.backtest.fees import calculate_fees
from dyadresearch.backtest.models import (
    ACTIVE_ORDER_STATUSES,
    EquityPoint,
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
    Trade,
)
from dyadresearch.backtest.policy import BacktestPolicy
from dyadresearch.data.models import Bar, CorporateAction


class Broker:
    def __init__(self, policy: BacktestPolicy) -> None:
        self.policy = policy
        self.cash = policy.initial_cash
        self.positions: dict[str, Position] = {}
        self.orders: list[Order] = []
        self._active_order_ids: set[int] = set()
        self._same_slice_order_ids: set[int] = set()
        self._unlimited_fill_order_ids: set[int] = set()
        self.trades: list[Trade] = []
        self.equity: list[EquityPoint] = []
        self._peak_assets = policy.initial_cash
        self.event_log: list[dict[str, object]] = []
        self.current_bars: dict[str, Bar] = {}
        self.now = 0
        self.sequence = 0
        self.trade_date: int | None = None

    @property
    def frozen_cash(self) -> Decimal:
        return sum(
            (self.orders[order_id - 1].frozen_cash for order_id in self._active_order_ids),
            Decimal("0"),
        )

    @property
    def available_cash(self) -> Decimal:
        return self.cash - self.frozen_cash

    def begin_slice(self, ts: int, sequence: int, bars: tuple[Bar, ...]) -> None:
        self.now = ts
        self.sequence = sequence
        self.current_bars = {bar.symbol: bar for bar in bars}
        current_date = bars[0].trade_date
        if self.trade_date is not None and current_date != self.trade_date:
            for position in self.positions.values():
                if self.policy.enforce_t1:
                    position.available_quantity += position.today_bought
                    position.today_bought = 0
        self.trade_date = current_date
        self.assert_invariants()

    def submit(
        self,
        symbol: str,
        side: Side,
        quantity: int,
        *,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Decimal | None = None,
        execute_on_current_slice: bool = False,
        ignore_volume_limit: bool = False,
        reservation_price: Decimal | None = None,
    ) -> Order:
        normalized = symbol.upper()
        order = Order(
            order_id=len(self.orders) + 1,
            symbol=normalized,
            side=side,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            submitted_ts=self.now,
            eligible_sequence=(
                self.sequence
                if execute_on_current_slice
                else self.sequence + self.policy.execution_delay_bars
            ),
        )
        self.orders.append(order)
        reason = self._submission_error(order, reservation_price=reservation_price)
        if reason is not None:
            order.status = OrderStatus.REJECTED
            order.reject_reason = reason
            self._log("order_rejected", order_id=order.order_id, reason=reason)
            return order
        bar = self.current_bars[normalized]
        reference = (
            reservation_price
            if reservation_price is not None
            else limit_price
            if limit_price is not None
            else bar.close
        )
        assert reference is not None
        if side is Side.BUY:
            order.frozen_cash = (
                reference * quantity + calculate_fees(self.policy, side, reference, quantity).total
            )
        else:
            position = self.positions[normalized]
            position.available_quantity -= quantity
            position.frozen_quantity += quantity
            order.frozen_quantity = quantity
        self._active_order_ids.add(order.order_id)
        if execute_on_current_slice:
            self._same_slice_order_ids.add(order.order_id)
        if ignore_volume_limit:
            self._unlimited_fill_order_ids.add(order.order_id)
        self._log("order_submitted", order_id=order.order_id)
        self.assert_invariants()
        return order

    def cancel(self, order_id: int, *, reason: str = "cancelled_by_strategy") -> Order | None:
        order = self.orders[order_id - 1] if 0 < order_id <= len(self.orders) else None
        if order is None or order.status not in ACTIVE_ORDER_STATUSES:
            return order
        self._release_reserve(order)
        order.status = OrderStatus.CANCELLED
        self._active_order_ids.discard(order.order_id)
        self._same_slice_order_ids.discard(order.order_id)
        self._unlimited_fill_order_ids.discard(order.order_id)
        order.reject_reason = reason
        self._log("order_cancelled", order_id=order.order_id, reason=reason)
        self.assert_invariants()
        return order

    def execute_pending(self) -> tuple[Trade, ...]:
        new_trades: list[Trade] = []
        capacity = {
            symbol: int(Decimal(bar.volume) * self.policy.max_volume_participation)
            for symbol, bar in self.current_bars.items()
        }
        for order_id in tuple(sorted(self._active_order_ids)):
            order = self.orders[order_id - 1]
            if order.status not in ACTIVE_ORDER_STATUSES:
                continue
            if self.sequence < order.eligible_sequence:
                continue
            if order.order_id not in self._same_slice_order_ids and self.now <= order.submitted_ts:
                continue
            bar = self.current_bars.get(order.symbol)
            if bar is None or not self._tradable(order, bar):
                continue
            price = self._match_price(order, bar)
            if price is None:
                continue
            order_capacity = (
                order.remaining_quantity
                if order.order_id in self._unlimited_fill_order_ids
                else capacity[order.symbol]
            )
            quantity = self._match_quantity(order, order_capacity)
            if quantity <= 0:
                continue
            if order.side is Side.BUY:
                quantity = self._affordable_quantity(order, price, quantity)
            if quantity <= 0:
                continue
            trade = self._apply_fill(order, quantity, price)
            if order.order_id not in self._unlimited_fill_order_ids:
                capacity[order.symbol] -= quantity
            new_trades.append(trade)
        self.assert_invariants()
        return tuple(new_trades)

    def apply_actions(self, actions: tuple[CorporateAction, ...]) -> None:
        if not self.policy.apply_corporate_actions:
            return
        for action in actions:
            position = self.positions.get(action.symbol)
            if position is None or position.quantity <= 0:
                continue
            for order in list(self.orders):
                if order.symbol == action.symbol and order.status in ACTIVE_ORDER_STATUSES:
                    self.cancel(order.order_id, reason="corporate_action_cancelled")
            old_quantity = position.quantity
            self.cash += action.interest * old_quantity
            bonus = int(Decimal(old_quantity) * (action.stock_bonus + action.stock_gift))
            rights = int(Decimal(old_quantity) * action.allot_num)
            rights_cost = action.allot_price * rights
            if rights_cost > self.available_cash:
                rights = 0
                rights_cost = Decimal("0")
            self.cash -= rights_cost
            added = bonus + rights
            if added:
                position.quantity += added
                position.available_quantity += added
                position.average_cost = (
                    position.average_cost * old_quantity + rights_cost
                ) / position.quantity
            self._log("corporate_action", symbol=action.symbol, added=added)
        self.assert_invariants()

    def mark_to_market(self) -> EquityPoint:
        position_value = Decimal("0")
        for symbol, position in self.positions.items():
            bar = self.current_bars.get(symbol)
            if bar is not None and bar.close is not None:
                position.last_price = bar.close
            position_value += position.last_price * position.quantity
        assets = self.cash + position_value
        self._peak_assets = max(self._peak_assets, assets)
        point = EquityPoint(
            ts=self.now,
            cash=self.cash,
            frozen_cash=self.frozen_cash,
            position_value=position_value,
            total_assets=assets,
            net_value=assets / self.policy.initial_cash,
            drawdown=(
                assets / self._peak_assets - Decimal("1") if self._peak_assets else Decimal("0")
            ),
        )
        self.equity.append(point)
        self.assert_invariants()
        return point

    def assert_invariants(self) -> None:
        if self.cash < 0 or self.available_cash < 0 or self.frozen_cash < 0:
            raise AssertionError("cash invariant violated")
        for position in self.positions.values():
            components = (
                position.available_quantity + position.today_bought + position.frozen_quantity
            )
            if position.quantity != components:
                raise AssertionError(
                    f"position invariant violated for {position.symbol}: "
                    f"{position.quantity} != {components}"
                )
            if (
                min(
                    position.quantity,
                    position.available_quantity,
                    position.today_bought,
                    position.frozen_quantity,
                )
                < 0
            ):
                raise AssertionError("position quantity cannot be negative")

    def max_affordable_quantity(self, price: Decimal, *, budget: Decimal | None = None) -> int:
        if price <= 0:
            return 0
        available = min(self.available_cash, budget) if budget is not None else self.available_cash
        if available <= 0:
            return 0
        quantity = int(available / price) // self.policy.buy_lot_size
        quantity *= self.policy.buy_lot_size
        while quantity > 0:
            fees = calculate_fees(self.policy, Side.BUY, price, quantity)
            if price * quantity + fees.total <= available:
                return quantity
            quantity -= self.policy.buy_lot_size
        return 0

    def total_assets_at_open(self) -> Decimal:
        position_value = Decimal("0")
        for symbol, position in self.positions.items():
            bar = self.current_bars.get(symbol)
            price = bar.open if bar is not None and bar.open is not None else position.last_price
            position_value += price * position.quantity
        return self.cash + position_value

    def record_event(self, event: str, **payload: object) -> None:
        self._log(event, **payload)

    def _submission_error(
        self, order: Order, *, reservation_price: Decimal | None = None
    ) -> str | None:
        if order.quantity <= 0:
            return "quantity_must_be_positive"
        if order.order_type is OrderType.LIMIT and order.limit_price is None:
            return "limit_price_required"
        bar = self.current_bars.get(order.symbol)
        if bar is None or (bar.close is None and reservation_price is None):
            return "no_current_market_data"
        if order.side is Side.BUY:
            if order.quantity % self.policy.buy_lot_size:
                return "buy_quantity_must_match_lot_size"
            reference = (
                reservation_price
                if reservation_price is not None
                else order.limit_price
                if order.limit_price is not None
                else bar.close
            )
            assert reference is not None
            required = (
                reference * order.quantity
                + calculate_fees(self.policy, order.side, reference, order.quantity).total
            )
            if required > self.available_cash:
                return "insufficient_cash"
        else:
            position = self.positions.get(order.symbol)
            if position is None or position.available_quantity < order.quantity:
                return "insufficient_available_position"
        return None

    def _tradable(self, order: Order, bar: Bar) -> bool:
        if bar.suspend_flag or bar.volume <= 0 or bar.open is None:
            return False
        if not self.policy.conservative_limit_board or bar.pre_close is None:
            return True
        upper = limit_price(bar.pre_close, self.policy.limit_ratio, upper=True)
        lower = limit_price(bar.pre_close, self.policy.limit_ratio, upper=False)
        if order.side is Side.BUY and bar.low is not None and bar.low >= upper:
            return False
        return not (order.side is Side.SELL and bar.high is not None and bar.high <= lower)

    def _match_price(self, order: Order, bar: Bar) -> Decimal | None:
        assert bar.open is not None
        price = bar.open
        if order.order_type is OrderType.LIMIT:
            assert order.limit_price is not None
            if order.side is Side.BUY:
                if bar.low is None or bar.low > order.limit_price:
                    return None
                price = min(bar.open, order.limit_price)
            else:
                if bar.high is None or bar.high < order.limit_price:
                    return None
                price = max(bar.open, order.limit_price)
        direction = Decimal("1") if order.side is Side.BUY else Decimal("-1")
        slipped = price * (Decimal("1") + direction * self.policy.slippage_bps / Decimal("10000"))
        rounding = ROUND_CEILING if order.side is Side.BUY else ROUND_FLOOR
        return (slipped / Decimal("0.01")).to_integral_value(rounding=rounding) * Decimal("0.01")

    def _match_quantity(self, order: Order, capacity: int) -> int:
        requested = min(order.remaining_quantity, capacity)
        if order.side is Side.BUY:
            requested = requested // self.policy.buy_lot_size * self.policy.buy_lot_size
        if not self.policy.allow_partial_fills and requested < order.remaining_quantity:
            return 0
        return requested

    def _affordable_quantity(self, order: Order, price: Decimal, requested: int) -> int:
        available = self.available_cash + order.frozen_cash
        quantity = requested
        fees = calculate_fees(self.policy, Side.BUY, price, quantity)
        if price * quantity + fees.total <= available:
            return quantity
        quantity = int(available / price) // self.policy.buy_lot_size * self.policy.buy_lot_size
        quantity = min(quantity, requested)
        while quantity > 0:
            fees = calculate_fees(self.policy, Side.BUY, price, quantity)
            if price * quantity + fees.total <= available:
                return quantity
            quantity -= self.policy.buy_lot_size
        return 0

    def _apply_fill(self, order: Order, quantity: int, price: Decimal) -> Trade:
        fees = calculate_fees(self.policy, order.side, price, quantity)
        old_notional = order.average_fill_price * order.filled_quantity
        if order.side is Side.BUY:
            order.frozen_cash = Decimal("0")
            total = price * quantity + fees.total
            self.cash -= total
            position = self.positions.setdefault(order.symbol, Position(order.symbol))
            position_cost = position.average_cost * position.quantity
            position.quantity += quantity
            position.today_bought += quantity
            if not self.policy.enforce_t1:
                position.today_bought -= quantity
                position.available_quantity += quantity
            position.average_cost = (position_cost + total) / position.quantity
            position.last_price = price
        else:
            position = self.positions[order.symbol]
            position.quantity -= quantity
            position.frozen_quantity -= quantity
            order.frozen_quantity -= quantity
            self.cash += price * quantity - fees.total
            position.last_price = price
            if position.quantity == 0:
                position.average_cost = Decimal("0")
        order.filled_quantity += quantity
        order.average_fill_price = (old_notional + price * quantity) / order.filled_quantity
        order.status = (
            OrderStatus.FILLED if order.remaining_quantity == 0 else OrderStatus.PARTIALLY_FILLED
        )
        if order.side is Side.BUY and order.remaining_quantity:
            bar = self.current_bars[order.symbol]
            assert bar.close is not None
            estimated = (
                bar.close * order.remaining_quantity
                + calculate_fees(self.policy, Side.BUY, bar.close, order.remaining_quantity).total
            )
            order.frozen_cash = min(estimated, self.available_cash)
        if order.status is OrderStatus.FILLED:
            self._release_reserve(order)
            self._active_order_ids.discard(order.order_id)
            self._same_slice_order_ids.discard(order.order_id)
            self._unlimited_fill_order_ids.discard(order.order_id)
        trade = Trade(
            trade_id=len(self.trades) + 1,
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=quantity,
            price=price,
            ts=self.now,
            fees=fees,
        )
        self.trades.append(trade)
        self._log("trade", trade_id=trade.trade_id, order_id=order.order_id)
        return trade

    def _release_reserve(self, order: Order) -> None:
        order.frozen_cash = Decimal("0")
        if order.frozen_quantity:
            position = self.positions[order.symbol]
            position.frozen_quantity -= order.frozen_quantity
            position.available_quantity += order.frozen_quantity
            order.frozen_quantity = 0

    def _log(self, event: str, **payload: object) -> None:
        self.event_log.append({"ts": self.now, "event": event, **payload})


def limit_price(previous_close: Decimal, ratio: Decimal, *, upper: bool) -> Decimal:
    direction = Decimal("1") if upper else Decimal("-1")
    return (previous_close * (Decimal("1") + direction * ratio)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
