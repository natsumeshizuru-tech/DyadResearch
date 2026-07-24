from __future__ import annotations

from typing import Any, Protocol

from dyadresearch.backtest.models import Side, Trade
from dyadresearch.data.models import Bar
from dyadresearch.strategy.sdk import Strategy, StrategyContext


class QmtStrategyProtocol(Protocol):
    def init(self, context: QmtContext) -> None: ...

    def handlebar(self, context: QmtContext) -> None: ...


class QmtContext:
    def __init__(self, core: StrategyContext) -> None:
        self._core = core
        self.barpos = -1
        self.stock_code: list[str] = []

    def set_universe(self, symbols: list[str]) -> None:
        self.stock_code = [symbol.upper() for symbol in symbols]

    def order_shares(self, symbol: str, quantity: int) -> int:
        side = Side.BUY if quantity > 0 else Side.SELL
        return self._core.order(symbol, abs(quantity), side=side).order_id

    def get_market_data_ex(
        self,
        field_list: list[str],
        stock_list: list[str],
        period: str = "1d",
        count: int = -1,
    ) -> dict[str, list[dict[str, Any]]]:
        if period not in {"1d", "1m"}:
            raise ValueError(f"QMT strategy history period is unsupported: {period}")
        output: dict[str, list[dict[str, Any]]] = {}
        for symbol in stock_list:
            bars = self._core.history(symbol, count if count > 0 else 1_000_000)
            output[symbol.upper()] = [
                {field: _qmt_value(bar, field) for field in field_list} for bar in bars
            ]
        return output

    def get_trade_detail_data(self, account: object, account_type: str, data_type: str) -> None:
        del account, account_type, data_type
        raise RuntimeError("trading/account APIs are forbidden in DyadResearch")


class QmtStrategyAdapter(Strategy):
    def __init__(self, strategy: QmtStrategyProtocol, symbols: list[str]) -> None:
        self.strategy = strategy
        self.symbols = symbols
        self.qmt_context: QmtContext | None = None

    def initialize(self, context: StrategyContext) -> None:
        self.qmt_context = QmtContext(context)
        self.qmt_context.set_universe(self.symbols)
        self.strategy.init(self.qmt_context)

    def on_bars(self, context: StrategyContext, bars: tuple[Bar, ...]) -> None:
        del context, bars
        assert self.qmt_context is not None
        self.qmt_context.barpos += 1
        self.strategy.handlebar(self.qmt_context)

    def on_trade(self, context: StrategyContext, trade: Trade) -> None:
        del context
        callback = getattr(self.strategy, "on_trade", None)
        if callable(callback):
            callback(self.qmt_context, trade)


def _qmt_value(bar: Bar, field: str) -> Any:
    field_map = {
        "time": "ts",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "amount": "amount",
        "preClose": "pre_close",
        "suspendFlag": "suspend_flag",
    }
    attribute = field_map.get(field)
    if attribute is None:
        raise ValueError(f"unsupported QMT field: {field}")
    return getattr(bar, attribute)
