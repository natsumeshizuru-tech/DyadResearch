from decimal import Decimal

import pytest

from dyadresearch.backtest.adapters import QmtContext, QmtStrategyAdapter
from dyadresearch.backtest.engine import BacktestEngine
from dyadresearch.backtest.models import Side
from dyadresearch.backtest.policy import BacktestPolicy
from dyadresearch.data.models import Bar
from dyadresearch.strategy.sdk import Strategy, StrategyContext


def bars() -> tuple[Bar, ...]:
    return tuple(
        Bar(
            symbol="000001.SZ",
            ts=index,
            trade_date=20250102 if index < 4 else 20250103,
            open=Decimal(str(9 + index)),
            high=Decimal(str(9 + index)),
            low=Decimal(str(9 + index)),
            close=Decimal(str(9 + index)),
            volume=1000,
            amount=Decimal(str((9 + index) * 1000)),
            pre_close=Decimal(str(9 + index)),
        )
        for index in range(1, 6)
    )


class NativeBuyOnce(Strategy):
    def __init__(self) -> None:
        self.called = False

    def on_bars(self, context: StrategyContext, current: tuple[Bar, ...]) -> None:
        del current
        if not self.called:
            context.order("000001.SZ", 100, side=Side.BUY)
            self.called = True


class QmtBuyOnce:
    def init(self, context: QmtContext) -> None:
        self.context = context

    def handlebar(self, context: QmtContext) -> None:
        if context.barpos == 0:
            context.order_shares("000001.SZ", 100)


def test_engine_is_deterministic_and_never_same_bar_fills() -> None:
    policy = BacktestPolicy(initial_cash=Decimal("100000"))
    first = BacktestEngine().run(
        NativeBuyOnce(), bars=bars(), data_fingerprint="fixed", policy=policy
    )
    second = BacktestEngine().run(
        NativeBuyOnce(), bars=bars(), data_fingerprint="fixed", policy=policy
    )
    assert first.result_hash == second.result_hash
    assert first.run_id == second.run_id
    assert first.orders[0].submitted_ts == 1
    assert first.trades[0].ts == 2
    assert first.trades[0].price == Decimal("11.00")


@pytest.mark.parity
def test_native_and_qmt_adapters_share_identical_kernel_results() -> None:
    policy = BacktestPolicy(initial_cash=Decimal("100000"))
    native = BacktestEngine().run(
        NativeBuyOnce(), bars=bars(), data_fingerprint="fixed", policy=policy
    )
    qmt = BacktestEngine().run(
        QmtStrategyAdapter(QmtBuyOnce(), ["000001.SZ"]),
        bars=bars(),
        data_fingerprint="fixed",
        policy=policy,
    )
    assert native.result_hash == qmt.result_hash
    assert native.trades == qmt.trades


def test_qmt_history_contains_no_future_bars() -> None:
    observed: list[int] = []

    class HistoryStrategy:
        def init(self, context: QmtContext) -> None:
            del context

        def handlebar(self, context: QmtContext) -> None:
            frame = context.get_market_data_ex(["time"], ["000001.SZ"], period="1d", count=99)
            observed.append(len(frame["000001.SZ"]))

    BacktestEngine().run(
        QmtStrategyAdapter(HistoryStrategy(), ["000001.SZ"]),
        bars=bars(),
        data_fingerprint="fixed",
        policy=BacktestPolicy(),
    )
    assert observed == [1, 2, 3, 4, 5]


def test_qmt_account_api_is_explicitly_forbidden() -> None:
    class AccountStrategy:
        def init(self, context: QmtContext) -> None:
            self.context = context

        def handlebar(self, context: QmtContext) -> None:
            context.get_trade_detail_data(None, "STOCK", "ACCOUNT")

    with pytest.raises(RuntimeError, match="forbidden"):
        BacktestEngine().run(
            QmtStrategyAdapter(AccountStrategy(), ["000001.SZ"]),
            bars=bars(),
            data_fingerprint="fixed",
            policy=BacktestPolicy(),
        )
