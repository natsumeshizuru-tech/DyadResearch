from decimal import Decimal

import pytest

from dyadresearch.backtest.broker import Broker
from dyadresearch.backtest.models import OrderStatus, OrderType, Position, Side
from dyadresearch.backtest.policy import BacktestPolicy
from dyadresearch.data.models import Bar, CorporateAction


def bar(
    ts: int,
    trade_date: int,
    *,
    price: str = "10",
    volume: int = 1000,
    suspend: int = 0,
    low: str | None = None,
    high: str | None = None,
    pre_close: str = "10",
) -> Bar:
    value = Decimal(price)
    return Bar(
        symbol="000001.SZ",
        ts=ts,
        trade_date=trade_date,
        open=value,
        high=Decimal(high) if high is not None else value,
        low=Decimal(low) if low is not None else value,
        close=value,
        volume=volume,
        amount=value * volume,
        pre_close=Decimal(pre_close),
        suspend_flag=suspend,
    )


def test_buy_is_frozen_then_filled_on_next_bar() -> None:
    broker = Broker(BacktestPolicy(initial_cash=Decimal("10000")))
    broker.begin_slice(1, 1, (bar(1, 20250102),))
    order = broker.submit("000001.SZ", Side.BUY, 100)
    assert order.status is OrderStatus.SUBMITTED
    assert broker.cash == Decimal("10000")
    assert broker.available_cash == Decimal("8995.0000")
    assert broker.execute_pending() == ()
    broker.begin_slice(2, 2, (bar(2, 20250102, price="11", pre_close="11"),))
    trades = broker.execute_pending()
    assert len(trades) == 1
    assert trades[0].price == Decimal("11.00")
    assert broker.positions["000001.SZ"].today_bought == 100
    assert broker.frozen_cash == 0


def test_t1_rejects_same_day_sell_and_allows_next_day() -> None:
    broker = Broker(BacktestPolicy(initial_cash=Decimal("10000")))
    broker.begin_slice(1, 1, (bar(1, 20250102),))
    broker.submit("000001.SZ", Side.BUY, 100)
    broker.begin_slice(2, 2, (bar(2, 20250102),))
    broker.execute_pending()
    rejected = broker.submit("000001.SZ", Side.SELL, 100)
    assert rejected.status is OrderStatus.REJECTED
    assert rejected.reject_reason == "insufficient_available_position"
    broker.begin_slice(3, 3, (bar(3, 20250103),))
    accepted = broker.submit("000001.SZ", Side.SELL, 100)
    assert accepted.status is OrderStatus.SUBMITTED
    assert broker.positions["000001.SZ"].frozen_quantity == 100


def test_partial_fills_share_one_bar_capacity() -> None:
    policy = BacktestPolicy(initial_cash=Decimal("100000"), max_volume_participation=Decimal("0.1"))
    broker = Broker(policy)
    broker.begin_slice(1, 1, (bar(1, 20250102),))
    first = broker.submit("000001.SZ", Side.BUY, 200)
    second = broker.submit("000001.SZ", Side.BUY, 200)
    broker.begin_slice(2, 2, (bar(2, 20250102),))
    trades = broker.execute_pending()
    assert [trade.quantity for trade in trades] == [100]
    assert first.status is OrderStatus.PARTIALLY_FILLED
    assert second.status is OrderStatus.SUBMITTED


def test_suspension_and_locked_limit_keep_order_pending() -> None:
    broker = Broker(BacktestPolicy(initial_cash=Decimal("10000")))
    broker.begin_slice(1, 1, (bar(1, 20250102),))
    order = broker.submit("000001.SZ", Side.BUY, 100)
    broker.begin_slice(2, 2, (bar(2, 20250102, suspend=1),))
    assert broker.execute_pending() == ()
    broker.begin_slice(
        3,
        3,
        (bar(3, 20250102, price="11", low="11", high="11", pre_close="10"),),
    )
    assert broker.execute_pending() == ()
    assert order.status is OrderStatus.SUBMITTED


def test_limit_order_only_fills_when_reached() -> None:
    broker = Broker(BacktestPolicy(initial_cash=Decimal("10000")))
    broker.begin_slice(1, 1, (bar(1, 20250102),))
    order = broker.submit(
        "000001.SZ",
        Side.BUY,
        100,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("9.5"),
    )
    broker.begin_slice(2, 2, (bar(2, 20250102, low="9.6", high="10"),))
    assert broker.execute_pending() == ()
    broker.begin_slice(3, 3, (bar(3, 20250102, low="9.4", high="10"),))
    assert broker.execute_pending()[0].price == Decimal("9.50")
    assert order.status is OrderStatus.FILLED


def test_cancel_releases_cash_and_position() -> None:
    broker = Broker(BacktestPolicy(initial_cash=Decimal("10000")))
    broker.begin_slice(1, 1, (bar(1, 20250102),))
    buy = broker.submit("000001.SZ", Side.BUY, 100)
    assert broker.cancel(buy.order_id).status is OrderStatus.CANCELLED
    assert broker.available_cash == broker.cash
    broker.positions["000001.SZ"] = Position("000001.SZ", quantity=100, available_quantity=100)
    sell = broker.submit("000001.SZ", Side.SELL, 100)
    broker.cancel(sell.order_id)
    assert broker.positions["000001.SZ"].available_quantity == 100


def test_corporate_action_cancels_orders_and_updates_position() -> None:
    broker = Broker(BacktestPolicy(initial_cash=Decimal("10000")))
    broker.positions["000001.SZ"] = Position(
        "000001.SZ",
        quantity=100,
        available_quantity=100,
        average_cost=Decimal("10"),
    )
    broker.begin_slice(1, 1, (bar(1, 20250102),))
    order = broker.submit("000001.SZ", Side.SELL, 100)
    action = CorporateAction(
        "000001.SZ",
        20250102,
        Decimal("0.1"),
        Decimal("0.1"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0.9"),
    )
    broker.apply_actions((action,))
    assert order.status is OrderStatus.CANCELLED
    assert broker.positions["000001.SZ"].quantity == 110
    assert broker.cash == Decimal("10010.0")


def test_invariant_detects_corrupt_position() -> None:
    broker = Broker(BacktestPolicy())
    broker.positions["000001.SZ"] = Position("000001.SZ", quantity=1)
    with pytest.raises(AssertionError, match="position invariant"):
        broker.assert_invariants()
