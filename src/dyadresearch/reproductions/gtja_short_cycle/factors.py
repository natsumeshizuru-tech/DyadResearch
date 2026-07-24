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
from dyadresearch.reproductions.common.operators import where
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
    if factor_id == "alpha143":
        return alpha143(inputs["close"])
    result = RestrictedExpression(record.normalized_expression).evaluate(inputs)
    if not isinstance(result, pd.DataFrame):
        raise TypeError(f"{factor_id} did not produce a panel")
    return result


def alpha143(close: pd.DataFrame) -> pd.DataFrame:
    output = close.copy() * float("nan")
    for position in range(1, len(close.index)):
        previous = output.iloc[position - 1].fillna(1.0)
        previous_close = close.iloc[position - 1]
        current_close = close.iloc[position]
        positive = current_close > previous_close
        one_day_return = (current_close - previous_close) / previous_close.replace(0, float("nan"))
        output.iloc[position] = where(
            pd.DataFrame([positive], index=[close.index[position]]),
            pd.DataFrame([previous * one_day_return], index=[close.index[position]]),
            pd.DataFrame([previous], index=[close.index[position]]),
        ).iloc[0]
    return output


def register_factor_specs() -> None:
    factor_registry.register(
        FactorSpec(
            name="gtja_alpha014",
            version="2026.07.25",
            description="GTJA Alpha 14: close minus five-session delayed close.",
            input_fields=("close",),
            lookback=6,
            frequency="1d",
            calculator=_alpha014_bar,
        ),
        replace=True,
    )


def _alpha014_bar(window: tuple[Bar, ...]) -> Decimal | None:
    current = window[-1].close
    previous = window[-6].close
    if current is None or previous is None:
        return None
    return current - previous
