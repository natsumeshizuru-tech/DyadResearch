import json
from decimal import Decimal
from pathlib import Path

from dyadresearch.backtest.engine import BacktestEngine
from dyadresearch.backtest.policy import BacktestPolicy
from dyadresearch.data.models import Bar
from dyadresearch.strategy.examples import BuyAndHoldStrategy


def test_strict_buy_hold_golden_contract() -> None:
    expected = json.loads(
        (Path(__file__).with_name("strict_buy_hold_v1.json")).read_text(encoding="utf-8")
    )
    bars = tuple(
        Bar(
            "000001.SZ",
            index,
            20250102,
            Decimal(str(9 + index)),
            Decimal(str(9 + index)),
            Decimal(str(9 + index)),
            Decimal(str(9 + index)),
            1000,
            Decimal(str((9 + index) * 1000)),
            pre_close=Decimal(str(9 + index)),
        )
        for index in range(1, 6)
    )
    result = BacktestEngine().run(
        BuyAndHoldStrategy("000001.SZ"),
        bars=bars,
        data_fingerprint=expected["data_fingerprint"],
        policy=BacktestPolicy(initial_cash=Decimal("100000")),
    )
    assert result.result_hash == expected["result_hash"]
    assert len(result.trades) == expected["trade_count"]
    assert result.trades[0].ts == expected["fill_ts"]
    assert result.trades[0].price == Decimal(expected["fill_price"])
    assert result.final_positions["000001.SZ"] == expected["final_quantity"]
