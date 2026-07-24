from __future__ import annotations

from contextlib import suppress
from decimal import Decimal
from statistics import pstdev

from dyadresearch.data.models import Bar
from dyadresearch.factors.registry import factor_registry
from dyadresearch.factors.spec import FactorSpec


def momentum(window: tuple[Bar, ...]) -> Decimal | None:
    first, last = window[0].close, window[-1].close
    if first is None or last is None or first == 0:
        return None
    return last / first - Decimal("1")


def close_volatility(window: tuple[Bar, ...]) -> Decimal | None:
    closes = [bar.close for bar in window]
    if any(value is None or value <= 0 for value in closes):
        return None
    valid = [value for value in closes if value is not None]
    returns = [float(valid[index] / valid[index - 1] - 1) for index in range(1, len(valid))]
    return Decimal(str(pstdev(returns))) if returns else Decimal("0")


def average_turnover(window: tuple[Bar, ...]) -> Decimal | None:
    values = [bar.amount for bar in window]
    if any(value is None for value in values):
        return None
    valid = [value for value in values if value is not None]
    return sum(valid, Decimal("0")) / len(valid)


EXAMPLE_FACTORS = (
    FactorSpec(
        "momentum_20",
        "1",
        "20-bar close-to-close momentum",
        ("close",),
        20,
        "1d",
        momentum,
    ),
    FactorSpec(
        "volatility_20",
        "1",
        "20-bar population volatility of simple returns",
        ("close",),
        20,
        "1d",
        close_volatility,
        higher_is_better=False,
    ),
    FactorSpec(
        "average_turnover_20",
        "1",
        "20-bar average traded amount",
        ("amount",),
        20,
        "1d",
        average_turnover,
    ),
)


def register_examples() -> None:
    for spec in EXAMPLE_FACTORS:
        with suppress(ValueError):
            factor_registry.register(spec)


register_examples()
