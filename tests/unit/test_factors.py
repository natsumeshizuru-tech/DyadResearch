from decimal import Decimal

import pytest

from dyadresearch.data.models import Bar
from dyadresearch.factors.evaluator import FactorEvaluator
from dyadresearch.factors.examples import close_volatility, momentum
from dyadresearch.factors.registry import FactorRegistry, factor_registry
from dyadresearch.factors.spec import FactorSpec


def make_bars(symbol: str, closes: list[str]) -> tuple[Bar, ...]:
    return tuple(
        Bar(
            symbol=symbol,
            ts=index,
            trade_date=20250100 + index,
            open=Decimal(value),
            high=Decimal(value),
            low=Decimal(value),
            close=Decimal(value),
            volume=100,
            amount=Decimal(value) * 100,
        )
        for index, value in enumerate(closes, start=1)
    )


def test_factor_spec_validates_inputs() -> None:
    with pytest.raises(ValueError, match="unknown"):
        FactorSpec("bad", "1", "bad", ("future",), 1, "1d", momentum)
    with pytest.raises(ValueError, match="positive"):
        FactorSpec("bad", "1", "bad", ("close",), 0, "1d", momentum)


def test_registry_is_deterministic_and_refuses_duplicates() -> None:
    registry = FactorRegistry()
    spec = FactorSpec("z", "1", "test", ("close",), 2, "1d", momentum)
    registry.register(spec)
    with pytest.raises(ValueError, match="already"):
        registry.register(spec)
    assert registry.get("z") is spec
    with pytest.raises(KeyError, match="unknown"):
        registry.get("missing")
    assert [item.name for item in factor_registry.list()] == [
        "average_turnover_20",
        "momentum_20",
        "volatility_20",
    ]


def test_factor_evaluation_is_repeatable_and_sorted() -> None:
    spec = FactorSpec("momentum_3", "1", "test", ("close",), 3, "1d", momentum)
    bars = make_bars("000002.SZ", ["10", "11", "12", "15"]) + make_bars(
        "000001.SZ", ["5", "5", "10"]
    )
    first = FactorEvaluator().evaluate(spec, bars, data_fingerprint="fixed")
    second = FactorEvaluator().evaluate(spec, bars, data_fingerprint="fixed")
    assert first.result_hash == second.result_hash
    assert first.coverage_ratio == 1
    assert first.observations[0].symbol == "000001.SZ"
    assert first.observations[0].value == Decimal("1")
    assert first.summary["count"] == 3


def test_example_calculators_handle_missing_and_volatility() -> None:
    missing = make_bars("000001.SZ", ["1", "2"])
    missing_bar = Bar(
        symbol="000001.SZ",
        ts=3,
        trade_date=20250103,
        open=None,
        high=None,
        low=None,
        close=None,
        volume=0,
        amount=None,
    )
    assert momentum((missing[0], missing_bar)) is None
    assert close_volatility(make_bars("000001.SZ", ["10", "11", "12"])) is not None
