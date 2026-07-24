from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from dyadresearch.data.models import Bar
from dyadresearch.factors.registry import factor_registry
from dyadresearch.factors.spec import FactorSpec
from dyadresearch.reproductions.common.expression_ast import RestrictedExpression
from dyadresearch.reproductions.common.metadata import FormulaStatus
from dyadresearch.reproductions.common.registry import FormulaRegistry


@lru_cache(maxsize=1)
def load_registry() -> FormulaRegistry:
    return FormulaRegistry.load(Path(__file__).with_name("manifest.yaml"))


def evaluate_panel_factor(factor_id: str, inputs: dict[str, Any]) -> pd.DataFrame:
    record = load_registry().get(factor_id)
    if record.formula_status in {
        FormulaStatus.NOT_IMPLEMENTED,
        FormulaStatus.UNAVAILABLE_DEPENDENCY,
    }:
        raise ValueError(f"{factor_id} is not executable: {record.formula_status.value}")
    result = RestrictedExpression(record.normalized_expression).evaluate(inputs)
    if not isinstance(result, pd.DataFrame):
        raise TypeError(f"{factor_id} did not produce a panel")
    return result


def register_factor_specs() -> None:
    factor_registry.register(
        FactorSpec(
            name="wq101_alpha101",
            version="2026.07.25",
            description="WorldQuant Alpha 101 formula adapter; safe use executes next session.",
            input_fields=("open", "high", "low", "close"),
            lookback=1,
            frequency="1d",
            calculator=_alpha101_bar,
        ),
        replace=True,
    )


def _alpha101_bar(window: tuple[Bar, ...]) -> Decimal | None:
    bar = window[-1]
    if bar.open is None or bar.high is None or bar.low is None or bar.close is None:
        return None
    return (bar.close - bar.open) / (bar.high - bar.low + Decimal("0.001"))
