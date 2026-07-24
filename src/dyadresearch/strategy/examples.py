from __future__ import annotations

from bisect import bisect_right
from decimal import Decimal
from typing import Protocol

from dyadresearch.backtest.models import OrderStatus, Side, Trade
from dyadresearch.data.models import Bar
from dyadresearch.strategy.sdk import Strategy, StrategyContext
from dyadresearch.strategy.universe import MarketSignal


class BuyAndHoldStrategy(Strategy):
    """Buy once on the next tradable open and hold through the end of the test.

    ``quantity=None`` is the research default: invest the requested share of available
    capital, rounded down to the market lot size after fees.  An explicit quantity is
    retained for CLI/QMT compatibility and deterministic adapter tests.
    """

    def __init__(
        self,
        symbol: str,
        quantity: int | None = None,
        *,
        allocation_ratio: Decimal = Decimal("1"),
    ) -> None:
        if quantity is not None and quantity <= 0:
            raise ValueError("buy-and-hold quantity must be positive")
        if not Decimal("0") < allocation_ratio <= Decimal("1"):
            raise ValueError("buy-and-hold allocation_ratio must be in (0, 1]")
        self.symbol = symbol.upper()
        self.quantity = quantity
        self.allocation_ratio = allocation_ratio
        self.entry_armed = False
        self.submitted = False

    def before_bars(self, context: StrategyContext) -> None:
        if not self.entry_armed or self.submitted or self.symbol not in context.current_symbols:
            return
        opening_price = context.opening_price(self.symbol)
        if opening_price is None or not context.is_tradable_at_open(self.symbol):
            return
        quantity = self.quantity
        if quantity is None:
            budget = context.total_assets_at_open * self.allocation_ratio
            quantity = context.max_affordable_quantity(opening_price, budget=budget)
        if quantity <= 0:
            self.submitted = True
            context.record(
                "buy_and_hold_entry_skipped",
                symbol=self.symbol,
                reason="insufficient_cash_for_one_lot",
                allocation_ratio=float(self.allocation_ratio),
            )
            return
        order = context.buy_on_open(self.symbol, quantity)
        self.submitted = True
        context.record(
            "buy_and_hold_entry_scheduled",
            symbol=self.symbol,
            quantity=quantity,
            opening_price=float(opening_price),
            allocation_ratio=(float(self.allocation_ratio) if self.quantity is None else None),
            sizing_mode=("max_affordable" if self.quantity is None else "fixed_quantity"),
            order_status=order.status.value,
            reject_reason=order.reject_reason,
        )

    def on_bars(self, context: StrategyContext, bars: tuple[Bar, ...]) -> None:
        if not self.entry_armed and any(bar.symbol == self.symbol for bar in bars):
            self.entry_armed = True
            context.record(
                "buy_and_hold_signal",
                symbol=self.symbol,
                execution="next_tradable_open",
            )


class MovingAverageCrossStrategy(Strategy):
    def __init__(self, symbol: str, *, fast: int = 5, slow: int = 20, quantity: int = 100) -> None:
        if not 1 <= fast < slow:
            raise ValueError("moving averages require 1 <= fast < slow")
        self.symbol = symbol.upper()
        self.fast = fast
        self.slow = slow
        self.quantity = quantity

    def on_bars(self, context: StrategyContext, bars: tuple[Bar, ...]) -> None:
        if not any(bar.symbol == self.symbol for bar in bars):
            return
        history = context.history(self.symbol, self.slow)
        if len(history) < self.slow or any(bar.close is None for bar in history):
            return
        closes = [bar.close for bar in history if bar.close is not None]
        fast_average = sum(closes[-self.fast :], Decimal("0")) / self.fast
        slow_average = sum(closes, Decimal("0")) / self.slow
        position = context.positions.get(self.symbol, 0)
        if fast_average > slow_average and position == 0:
            context.order(self.symbol, self.quantity)
        elif fast_average < slow_average and position > 0:
            context.order(self.symbol, position, side=Side.SELL)


class LowVolumeRatioMomentumStrategy(Strategy):
    """Single-symbol execution of the main-board low-volume momentum rule.

    The web layer selects a research symbol and supplies point-in-time share capital and
    previous daily closes. The signal itself is evaluated on truthful one-minute bars.
    """

    def __init__(
        self,
        symbol: str,
        *,
        capital_schedule: tuple[tuple[int, Decimal], ...],
        previous_closes: dict[int, Decimal],
        market_cap_max: Decimal = Decimal("30000000000"),
        rise_threshold: Decimal = Decimal("0.07"),
        volume_ratio_max: Decimal = Decimal("0.6"),
        volume_lookback_days: int = 5,
        expected_minutes_per_day: int = 240,
        allocation_ratio: Decimal = Decimal("0.20"),
        limit_ratio: Decimal = Decimal("0.10"),
    ) -> None:
        if not is_main_board_symbol(symbol):
            raise ValueError("low-volume momentum requires a Shanghai/Shenzhen main-board stock")
        if not capital_schedule:
            raise ValueError("low-volume momentum requires point-in-time share-capital data")
        if volume_lookback_days < 1:
            raise ValueError("volume_lookback_days must be positive")
        if not Decimal("0") < allocation_ratio <= Decimal("1"):
            raise ValueError("allocation_ratio must be in (0, 1]")
        self.symbol = symbol.upper()
        self.capital_schedule = tuple(sorted(capital_schedule))
        self.previous_closes = previous_closes
        self.market_cap_max = market_cap_max
        self.rise_threshold = rise_threshold
        self.volume_ratio_max = volume_ratio_max
        self.volume_lookback_days = volume_lookback_days
        self.expected_minutes_per_day = expected_minutes_per_day
        self.allocation_ratio = allocation_ratio
        self.limit_ratio = limit_ratio
        self.current_date: int | None = None
        self.current_volume = 0
        self.current_minutes = 0
        self.completed_daily_volumes: list[int] = []
        self.entry_order_id: int | None = None
        self.entry_trade_date: int | None = None
        self.exit_order_id: int | None = None
        self.pending_signal: tuple[int, Decimal, Decimal, Decimal, Decimal] | None = None
        self.processed_signal_dates: set[int] = set()

    def before_bars(self, context: StrategyContext) -> None:
        trade_date = context.trade_date
        if trade_date is not None and self.entry_trade_date is not None:
            position = context.positions.get(self.symbol, 0)
            if trade_date > self.entry_trade_date and position > 0 and self.exit_order_id is None:
                if self.entry_order_id is not None:
                    context.cancel(
                        self.entry_order_id,
                        reason="next_session_cancel_entry_remainder",
                    )
                order = context.sell_on_open(self.symbol, position)
                if order.status is not OrderStatus.REJECTED:
                    self.exit_order_id = order.order_id
                    context.record(
                        "low_volume_ratio_exit_scheduled",
                        symbol=self.symbol,
                        quantity=position,
                        entry_trade_date=self.entry_trade_date,
                        exit_trade_date=trade_date,
                    )
        if self.pending_signal is None or trade_date is None:
            return
        signal_date, price_gain, volume_ratio, market_cap, previous_close = self.pending_signal
        self.pending_signal = None
        opening_price = context.opening_price(self.symbol)
        if (
            trade_date != signal_date
            or opening_price is None
            or not context.is_tradable_at_open(self.symbol)
        ):
            context.record(
                "low_volume_ratio_entry_skipped",
                symbol=self.symbol,
                reason="next_minute_open_unavailable",
                signal_trade_date=signal_date,
            )
            return
        if context.is_open_at_upper_limit(
            self.symbol,
            self.limit_ratio,
            previous_close=previous_close,
        ):
            context.record(
                "low_volume_ratio_entry_skipped",
                symbol=self.symbol,
                reason="next_minute_open_at_upper_limit",
                signal_trade_date=signal_date,
                opening_price=float(opening_price),
            )
            return
        budget = context.total_assets_at_open * self.allocation_ratio
        quantity = context.max_affordable_quantity(opening_price, budget=budget)
        if quantity <= 0:
            context.record(
                "low_volume_ratio_entry_skipped",
                symbol=self.symbol,
                reason="insufficient_allocation_cash",
                signal_trade_date=signal_date,
            )
            return
        order = context.buy_on_open(self.symbol, quantity)
        if order.status is not OrderStatus.REJECTED:
            self.entry_order_id = order.order_id
            context.record(
                "low_volume_ratio_entry_scheduled",
                symbol=self.symbol,
                trade_date=signal_date,
                price_gain=float(price_gain),
                volume_ratio=float(volume_ratio),
                market_cap=float(market_cap),
                allocation_ratio=float(self.allocation_ratio),
                quantity=quantity,
                opening_price=float(opening_price),
            )

    def on_bars(self, context: StrategyContext, bars: tuple[Bar, ...]) -> None:
        if self.entry_order_id is not None:
            entry = context.cancel(
                self.entry_order_id,
                reason="next_minute_open_entry_expired",
            )
            if (
                entry is not None
                and entry.status is OrderStatus.CANCELLED
                and context.positions.get(self.symbol, 0) == 0
            ):
                self.entry_order_id = None
        bar = next((item for item in bars if item.symbol == self.symbol), None)
        if bar is None or bar.close is None:
            return
        self._accumulate_volume(bar)
        if (
            context.positions.get(self.symbol, 0) > 0
            or self.entry_order_id is not None
            or self.pending_signal is not None
            or bar.trade_date in self.processed_signal_dates
        ):
            return
        previous_close = self.previous_closes.get(bar.trade_date)
        shares = self._shares_for_date(bar.trade_date)
        if previous_close is None or previous_close <= 0 or shares is None:
            return
        if bar.close * shares >= self.market_cap_max:
            return
        price_gain = bar.close / previous_close - Decimal("1")
        volume_ratio = self._volume_ratio()
        if price_gain <= self.rise_threshold or volume_ratio is None:
            return
        if volume_ratio >= self.volume_ratio_max:
            return
        self.processed_signal_dates.add(bar.trade_date)
        self.pending_signal = (
            bar.trade_date,
            price_gain,
            volume_ratio,
            bar.close * shares,
            previous_close,
        )
        context.record(
            "low_volume_ratio_signal",
            symbol=self.symbol,
            trade_date=bar.trade_date,
            price_gain=float(price_gain),
            volume_ratio=float(volume_ratio),
            market_cap=float(bar.close * shares),
            allocation_ratio=float(self.allocation_ratio),
        )

    def on_trade(self, context: StrategyContext, trade: Trade) -> None:
        if trade.symbol != self.symbol:
            return
        if trade.side is Side.BUY:
            self.entry_trade_date = context.trade_date
        else:
            if context.positions.get(self.symbol, 0) == 0:
                self.entry_trade_date = None
                self.entry_order_id = None
                self.exit_order_id = None

    def _accumulate_volume(self, bar: Bar) -> None:
        if self.current_date != bar.trade_date:
            if self.current_date is not None:
                self.completed_daily_volumes.append(self.current_volume)
            self.current_date = bar.trade_date
            self.current_volume = 0
            self.current_minutes = 0
        self.current_volume += max(0, bar.volume)
        self.current_minutes += 1

    def _volume_ratio(self) -> Decimal | None:
        history = self.completed_daily_volumes[-self.volume_lookback_days :]
        if len(history) < self.volume_lookback_days or not any(history):
            return None
        average_daily = Decimal(sum(history)) / len(history)
        elapsed = Decimal(min(self.current_minutes, self.expected_minutes_per_day))
        expected_volume = average_daily * elapsed / self.expected_minutes_per_day
        if expected_volume <= 0:
            return None
        return Decimal(self.current_volume) / expected_volume

    def _shares_for_date(self, trade_date: int) -> Decimal | None:
        keys = [item[0] for item in self.capital_schedule]
        index = bisect_right(keys, trade_date) - 1
        return None if index < 0 else self.capital_schedule[index][1]


class FullMarketLowVolumeRatioMomentumStrategy(Strategy):
    """Hold at most five equal-weight positions from full-market minute signals."""

    def __init__(
        self,
        signals: tuple[MarketSignal, ...],
        *,
        allocation_ratio: Decimal = Decimal("0.20"),
        max_positions: int = 5,
    ) -> None:
        if not signals:
            raise ValueError("full-market low-volume momentum requires at least one signal")
        if not Decimal("0") < allocation_ratio <= Decimal("1"):
            raise ValueError("allocation_ratio must be in (0, 1]")
        if max_positions < 1 or allocation_ratio * max_positions > Decimal("1"):
            raise ValueError("allocation ratio and max positions exceed total portfolio")
        self.signal_by_key = {(item.symbol, item.ts): item for item in signals}
        self.allocation_ratio = allocation_ratio
        self.max_positions = max_positions
        self.pending_signals: dict[str, MarketSignal] = {}
        self.entry_order_ids: dict[str, int] = {}
        self.entry_trade_dates: dict[str, int] = {}
        self.exit_order_ids: dict[str, int] = {}

    def before_bars(self, context: StrategyContext) -> None:
        trade_date = context.trade_date
        if trade_date is None:
            return
        for symbol, entry_date in tuple(self.entry_trade_dates.items()):
            position = context.positions.get(symbol, 0)
            if (
                trade_date <= entry_date
                or position <= 0
                or symbol not in context.current_symbols
                or symbol in self.exit_order_ids
            ):
                continue
            if symbol in self.entry_order_ids:
                context.cancel(
                    self.entry_order_ids[symbol],
                    reason="next_session_cancel_entry_remainder",
                )
            order = context.sell_on_open(symbol, position)
            if order.status is not OrderStatus.REJECTED:
                self.exit_order_ids[symbol] = order.order_id
                context.record(
                    "full_market_exit_scheduled",
                    symbol=symbol,
                    quantity=position,
                    entry_trade_date=entry_date,
                    exit_trade_date=trade_date,
                )

        ready = sorted(
            (
                signal
                for symbol, signal in self.pending_signals.items()
                if symbol in context.current_symbols
            ),
            key=lambda item: (-item.price_gain, item.volume_ratio, item.symbol),
        )
        for signal in ready:
            self.pending_signals.pop(signal.symbol, None)
            active_symbols = set(context.positions) | set(self.entry_order_ids)
            if len(active_symbols) >= self.max_positions:
                context.record(
                    "full_market_entry_skipped",
                    symbol=signal.symbol,
                    reason="portfolio_position_limit",
                    max_positions=self.max_positions,
                )
                continue
            opening_price = context.opening_price(signal.symbol)
            if (
                opening_price is None
                or trade_date != signal.trade_date
                or not context.is_tradable_at_open(signal.symbol)
            ):
                context.record(
                    "full_market_entry_skipped",
                    symbol=signal.symbol,
                    reason="next_minute_open_unavailable",
                )
                continue
            if context.is_open_at_upper_limit(
                signal.symbol,
                signal.limit_ratio,
                previous_close=signal.previous_close,
            ):
                context.record(
                    "full_market_entry_skipped",
                    symbol=signal.symbol,
                    reason="next_minute_open_at_upper_limit",
                    opening_price=float(opening_price),
                )
                continue
            budget = context.total_assets_at_open * self.allocation_ratio
            quantity = context.max_affordable_quantity(opening_price, budget=budget)
            if quantity <= 0:
                context.record(
                    "full_market_entry_skipped",
                    symbol=signal.symbol,
                    reason="insufficient_allocation_cash",
                )
                continue
            order = context.buy_on_open(signal.symbol, quantity)
            if order.status is not OrderStatus.REJECTED:
                self.entry_order_ids[signal.symbol] = order.order_id
                context.record(
                    "full_market_entry_scheduled",
                    symbol=signal.symbol,
                    quantity=quantity,
                    opening_price=float(opening_price),
                    allocation_ratio=float(self.allocation_ratio),
                )

    def on_bars(self, context: StrategyContext, bars: tuple[Bar, ...]) -> None:
        for symbol, order_id in tuple(self.entry_order_ids.items()):
            entry = context.cancel(order_id, reason="next_minute_open_entry_expired")
            if (
                entry is not None
                and entry.status is OrderStatus.CANCELLED
                and context.positions.get(symbol, 0) == 0
            ):
                self.entry_order_ids.pop(symbol, None)
        matches = [
            (self.signal_by_key[(bar.symbol, bar.ts)], bar)
            for bar in bars
            if (bar.symbol, bar.ts) in self.signal_by_key and bar.close is not None
        ]
        if not matches:
            return
        for signal, _bar in sorted(
            matches,
            key=lambda item: (-item[0].price_gain, item[0].volume_ratio, item[0].symbol),
        ):
            if (
                signal.symbol in context.positions
                or signal.symbol in self.entry_order_ids
                or signal.symbol in self.pending_signals
            ):
                continue
            self.pending_signals[signal.symbol] = signal
            context.record(
                "full_market_low_volume_ratio_signal",
                symbol=signal.symbol,
                trade_date=signal.trade_date,
                price_gain=float(signal.price_gain),
                volume_ratio=float(signal.volume_ratio),
                market_cap=float(signal.market_cap),
                allocation_ratio=float(self.allocation_ratio),
            )

    def on_trade(self, context: StrategyContext, trade: Trade) -> None:
        if trade.side is Side.BUY:
            if context.trade_date is not None:
                self.entry_trade_dates[trade.symbol] = context.trade_date
        elif context.positions.get(trade.symbol, 0) == 0:
            self.entry_order_ids.pop(trade.symbol, None)
            self.entry_trade_dates.pop(trade.symbol, None)
            self.exit_order_ids.pop(trade.symbol, None)


def is_main_board_symbol(symbol: str) -> bool:
    normalized = symbol.upper()
    code, _, market = normalized.partition(".")
    if market == "SH":
        return code.startswith(("600", "601", "603", "605"))
    if market == "SZ":
        return code.startswith(("000", "001", "002", "003"))
    return False


class QmtExampleContext(Protocol):
    barpos: int

    def set_universe(self, symbols: list[str]) -> None: ...

    def order_shares(self, symbol: str, quantity: int) -> int: ...


class QmtBuyAndHoldStrategy:
    def __init__(self, symbol: str, quantity: int = 100) -> None:
        self.symbol = symbol.upper()
        self.quantity = quantity

    def init(self, context: QmtExampleContext) -> None:
        context.set_universe([self.symbol])

    def handlebar(self, context: QmtExampleContext) -> None:
        if context.barpos == 0:
            context.order_shares(self.symbol, self.quantity)
