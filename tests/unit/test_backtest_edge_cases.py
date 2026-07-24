from dataclasses import replace
from decimal import Decimal

import pytest

from dyadresearch.backtest.adapters import QmtContext, QmtStrategyAdapter
from dyadresearch.backtest.broker import Broker
from dyadresearch.backtest.engine import BacktestEngine, _metrics
from dyadresearch.backtest.models import OrderStatus, OrderType, Position, Side
from dyadresearch.backtest.policy import BacktestPolicy
from dyadresearch.data.models import Bar, CorporateAction
from dyadresearch.strategy.sdk import Strategy, StrategyContext


def market_bar(
    ts: int,
    *,
    symbol: str = "000001.SZ",
    price: str = "10",
    volume: int = 1000,
    trade_date: int = 20250102,
) -> Bar:
    value = Decimal(price)
    return Bar(
        symbol=symbol,
        ts=ts,
        trade_date=trade_date,
        open=value,
        high=value,
        low=value,
        close=value,
        volume=volume,
        amount=value * volume,
        pre_close=value,
    )


@pytest.mark.parametrize(
    ("quantity", "order_type", "limit_price", "symbol", "reason"),
    [
        (0, OrderType.MARKET, None, "000001.SZ", "quantity_must_be_positive"),
        (100, OrderType.LIMIT, None, "000001.SZ", "limit_price_required"),
        (100, OrderType.MARKET, None, "000002.SZ", "no_current_market_data"),
        (50, OrderType.MARKET, None, "000001.SZ", "buy_quantity_must_match_lot_size"),
    ],
)
def test_submission_rejection_reasons(
    quantity: int,
    order_type: OrderType,
    limit_price: Decimal | None,
    symbol: str,
    reason: str,
) -> None:
    broker = Broker(BacktestPolicy(initial_cash=Decimal("10000")))
    broker.begin_slice(1, 1, (market_bar(1),))
    order = broker.submit(
        symbol, Side.BUY, quantity, order_type=order_type, limit_price=limit_price
    )
    assert order.status is OrderStatus.REJECTED
    assert order.reject_reason == reason


def test_insufficient_cash_and_cancel_non_active() -> None:
    broker = Broker(BacktestPolicy(initial_cash=Decimal("100")))
    broker.begin_slice(1, 1, (market_bar(1),))
    order = broker.submit("000001.SZ", Side.BUY, 100)
    assert order.reject_reason == "insufficient_cash"
    assert broker.cancel(999) is None
    assert broker.cancel(order.order_id) is order


def test_gap_affordability_shrinks_or_defers_buy() -> None:
    broker = Broker(BacktestPolicy(initial_cash=Decimal("3000")))
    broker.begin_slice(1, 1, (market_bar(1, price="10"),))
    order = broker.submit("000001.SZ", Side.BUY, 200)
    broker.begin_slice(2, 2, (market_bar(2, price="20"),))
    trade = broker.execute_pending()[0]
    assert trade.quantity == 100
    assert order.status is OrderStatus.PARTIALLY_FILLED

    second = Broker(BacktestPolicy(initial_cash=Decimal("3000")))
    second.begin_slice(1, 1, (market_bar(1, price="10"),))
    pending = second.submit("000001.SZ", Side.BUY, 200)
    second.begin_slice(2, 2, (market_bar(2, price="100"),))
    assert second.execute_pending() == ()
    assert pending.status is OrderStatus.SUBMITTED


def test_no_partial_fill_policy_and_zero_volume_defer() -> None:
    broker = Broker(
        BacktestPolicy(
            initial_cash=Decimal("10000"),
            max_volume_participation=Decimal("0.1"),
            allow_partial_fills=False,
        )
    )
    broker.begin_slice(1, 1, (market_bar(1),))
    order = broker.submit("000001.SZ", Side.BUY, 200)
    broker.begin_slice(2, 2, (market_bar(2, volume=1000),))
    assert broker.execute_pending() == ()
    broker.begin_slice(3, 3, (market_bar(3, volume=0),))
    assert broker.execute_pending() == ()
    assert order.status is OrderStatus.SUBMITTED


def test_sell_limit_odd_lot_and_non_t1_buy() -> None:
    policy = BacktestPolicy(initial_cash=Decimal("10000"), enforce_t1=False)
    broker = Broker(policy)
    broker.begin_slice(1, 1, (market_bar(1),))
    broker.submit("000001.SZ", Side.BUY, 100)
    broker.begin_slice(2, 2, (market_bar(2),))
    broker.execute_pending()
    assert broker.positions["000001.SZ"].available_quantity == 100
    sell = broker.submit(
        "000001.SZ",
        Side.SELL,
        50,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("11"),
    )
    broker.begin_slice(3, 3, (market_bar(3, price="10"),))
    assert broker.execute_pending() == ()
    broker.begin_slice(4, 4, (replace(market_bar(4, price="10"), high=Decimal("12")),))
    trade = broker.execute_pending()[0]
    assert trade.quantity == 50
    assert trade.price == Decimal("11.00")
    assert sell.status is OrderStatus.FILLED


def test_locked_sell_and_relaxed_limit_policy() -> None:
    position = Position("000001.SZ", quantity=100, available_quantity=100)
    broker = Broker(BacktestPolicy(initial_cash=Decimal("10000")))
    broker.positions[position.symbol] = position
    broker.begin_slice(1, 1, (market_bar(1),))
    sell = broker.submit("000001.SZ", Side.SELL, 100)
    locked = replace(
        market_bar(2, price="9"),
        pre_close=Decimal("10"),
        high=Decimal("9"),
        low=Decimal("9"),
    )
    broker.begin_slice(2, 2, (locked,))
    assert broker.execute_pending() == ()
    assert sell.status is OrderStatus.SUBMITTED

    relaxed = Broker(BacktestPolicy(initial_cash=Decimal("10000"), conservative_limit_board=False))
    relaxed.begin_slice(1, 1, (market_bar(1),))
    relaxed.submit("000001.SZ", Side.BUY, 100)
    relaxed.begin_slice(2, 2, (replace(locked, open=Decimal("11"), close=Decimal("11")),))
    assert len(relaxed.execute_pending()) == 1


def test_actions_disabled_missing_position_and_unaffordable_rights() -> None:
    action = CorporateAction(
        "000001.SZ",
        20250102,
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("1"),
        Decimal("1000"),
        Decimal("1"),
    )
    disabled = Broker(BacktestPolicy(apply_corporate_actions=False))
    disabled.apply_actions((action,))
    assert disabled.event_log == []
    broker = Broker(BacktestPolicy(initial_cash=Decimal("10")))
    broker.apply_actions((action,))
    broker.positions["000001.SZ"] = Position(
        "000001.SZ", quantity=100, available_quantity=100, average_cost=Decimal("10")
    )
    broker.apply_actions((action,))
    assert broker.positions["000001.SZ"].quantity == 100
    assert broker.cash == Decimal("10")


def test_mark_uses_last_price_and_invariants_detect_corruption() -> None:
    broker = Broker(BacktestPolicy(initial_cash=Decimal("100")))
    broker.positions["000002.SZ"] = Position(
        "000002.SZ", quantity=2, available_quantity=2, last_price=Decimal("3")
    )
    broker.begin_slice(1, 1, (market_bar(1),))
    assert broker.mark_to_market().position_value == Decimal("6")
    broker.cash = Decimal("-1")
    with pytest.raises(AssertionError, match="cash invariant"):
        broker.assert_invariants()
    broker.cash = Decimal("100")
    broker.positions["000002.SZ"] = Position("000002.SZ", quantity=-1, available_quantity=-1)
    with pytest.raises(AssertionError, match="cannot be negative"):
        broker.assert_invariants()


def test_engine_empty_metrics_and_default_strategy_hooks() -> None:
    with pytest.raises(ValueError, match="at least one bar"):
        BacktestEngine().run(Strategy(), bars=(), data_fingerprint="empty", policy=BacktestPolicy())
    broker = Broker(BacktestPolicy())
    assert _metrics(broker) == {}
    context = StrategyContext(broker)
    strategy = Strategy()
    strategy.initialize(context)
    strategy.on_start(context)
    strategy.on_bars(context, ())
    strategy.on_stop(context)
    assert context.now == 0
    assert context.cash == broker.available_cash
    assert context.positions == {}
    assert context.cancel(999) is None


def test_qmt_adapter_validation_unknown_field_and_trade_callback() -> None:
    observed: list[int] = []

    class WithTrade:
        def init(self, context: QmtContext) -> None:
            self.context = context

        def handlebar(self, context: QmtContext) -> None:
            if context.barpos == 0:
                context.order_shares("000001.SZ", 100)

        def on_trade(self, context: QmtContext, trade: object) -> None:
            del context, trade
            observed.append(1)

    result = BacktestEngine().run(
        QmtStrategyAdapter(WithTrade(), ["000001.SZ"]),
        bars=(market_bar(1), market_bar(2)),
        data_fingerprint="qmt",
        policy=BacktestPolicy(initial_cash=Decimal("10000")),
    )
    assert len(result.trades) == 1
    assert observed == [1]

    class InvalidHistory:
        def init(self, context: QmtContext) -> None:
            self.context = context

        def handlebar(self, context: QmtContext) -> None:
            context.get_market_data_ex(["unknown"], ["000001.SZ"])

    with pytest.raises(ValueError, match="unsupported QMT field"):
        BacktestEngine().run(
            QmtStrategyAdapter(InvalidHistory(), ["000001.SZ"]),
            bars=(market_bar(1),),
            data_fingerprint="bad",
            policy=BacktestPolicy(),
        )
    context = QmtContext(StrategyContext(Broker(BacktestPolicy())))
    with pytest.raises(ValueError, match="history period"):
        context.get_market_data_ex(["close"], ["000001.SZ"], period="tick")
