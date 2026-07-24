from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from dyadresearch.backtest.broker import Broker, limit_price
from dyadresearch.backtest.models import Order, OrderType, Side, Trade
from dyadresearch.data.models import Bar


class StrategyContext:
    def __init__(self, broker: Broker) -> None:
        self._broker = broker
        self._history_by_symbol: dict[str, list[Bar]] = defaultdict(list)
        self.current_bars: tuple[Bar, ...] = ()

    @property
    def now(self) -> int:
        return self._broker.now

    @property
    def cash(self) -> Decimal:
        return self._broker.available_cash

    @property
    def positions(self) -> dict[str, int]:
        return {
            symbol: position.quantity
            for symbol, position in self._broker.positions.items()
            if position.quantity
        }

    @property
    def trade_date(self) -> int | None:
        return self._broker.trade_date

    @property
    def current_symbols(self) -> tuple[str, ...]:
        return tuple(sorted(self._broker.current_bars))

    def order(
        self,
        symbol: str,
        quantity: int,
        *,
        side: Side = Side.BUY,
        limit_price: Decimal | None = None,
    ) -> Order:
        order_type = OrderType.LIMIT if limit_price is not None else OrderType.MARKET
        return self._broker.submit(
            symbol, side, quantity, order_type=order_type, limit_price=limit_price
        )

    def cancel(self, order_id: int, *, reason: str = "cancelled_by_strategy") -> Order | None:
        return self._broker.cancel(order_id, reason=reason)

    def sell_on_open(self, symbol: str, quantity: int) -> Order:
        return self._broker.submit(
            symbol,
            Side.SELL,
            quantity,
            execute_on_current_slice=True,
            ignore_volume_limit=True,
        )

    def buy_on_open(self, symbol: str, quantity: int) -> Order:
        bar = self._broker.current_bars.get(symbol.upper())
        if bar is None or bar.open is None:
            return self._broker.submit(symbol, Side.BUY, quantity)
        return self._broker.submit(
            symbol,
            Side.BUY,
            quantity,
            execute_on_current_slice=True,
            ignore_volume_limit=True,
            reservation_price=bar.open,
        )

    def order_full_market(self, symbol: str, quantity: int) -> Order:
        return self._broker.submit(symbol, Side.BUY, quantity, ignore_volume_limit=True)

    def max_affordable_quantity(self, price: Decimal, *, budget: Decimal | None = None) -> int:
        return self._broker.max_affordable_quantity(price, budget=budget)

    @property
    def total_assets_at_open(self) -> Decimal:
        return self._broker.total_assets_at_open()

    def opening_price(self, symbol: str) -> Decimal | None:
        bar = self._broker.current_bars.get(symbol.upper())
        return None if bar is None else bar.open

    def is_tradable_at_open(self, symbol: str) -> bool:
        bar = self._broker.current_bars.get(symbol.upper())
        return bool(
            bar is not None and bar.open is not None and bar.volume > 0 and not bar.suspend_flag
        )

    def is_open_at_upper_limit(
        self,
        symbol: str,
        ratio: Decimal,
        *,
        previous_close: Decimal | None = None,
    ) -> bool:
        bar = self._broker.current_bars.get(symbol.upper())
        reference = previous_close if previous_close is not None else bar.pre_close if bar else None
        if bar is None or bar.open is None or reference is None:
            return False
        return bar.open >= limit_price(reference, ratio, upper=True)

    def record(self, event: str, **payload: object) -> None:
        self._broker.record_event(event, **payload)

    def history(self, symbol: str, count: int) -> tuple[Bar, ...]:
        selected = self._history_by_symbol.get(symbol.upper(), [])
        return tuple(selected[-count:])

    def _publish(self, bars: tuple[Bar, ...]) -> None:
        self.current_bars = bars
        for bar in bars:
            self._history_by_symbol[bar.symbol].append(bar)


class Strategy:
    version = "1"

    def initialize(self, context: StrategyContext) -> None:
        del context

    def on_start(self, context: StrategyContext) -> None:
        del context

    def before_bars(self, context: StrategyContext) -> None:
        """Run before the current slice executes, with history ending at the prior slice."""
        del context

    def on_bars(self, context: StrategyContext, bars: tuple[Bar, ...]) -> None:
        del context, bars

    def on_trade(self, context: StrategyContext, trade: Trade) -> None:
        del context, trade

    def on_stop(self, context: StrategyContext) -> None:
        del context
