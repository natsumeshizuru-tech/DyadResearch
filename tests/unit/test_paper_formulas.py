from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dyadresearch.reproductions.common.expression_ast import RestrictedExpression
from dyadresearch.reproductions.common.metadata import FormulaStatus
from dyadresearch.reproductions.common.operators import (
    correlation,
    delay,
    rank,
    ts_argmax,
)
from dyadresearch.reproductions.common.registry import FormulaRegistry
from dyadresearch.reproductions.gtja_short_cycle.factors import alpha143
from dyadresearch.reproductions.paper_runner import audit_paper


def _panel(rows: int = 12, columns: int = 4) -> pd.DataFrame:
    values = np.arange(1, rows * columns + 1, dtype=float).reshape(rows, columns)
    return pd.DataFrame(values, columns=[f"S{item}" for item in range(columns)])


def test_operator_semantics_cover_rank_delay_correlation_and_noninteger_window() -> None:
    value = _panel()
    assert rank(value).iloc[0].tolist() == [0.25, 0.5, 0.75, 1.0]
    assert delay(value, 2.9).iloc[2].equals(value.iloc[0])
    direct = value.iloc[:, 0].rolling(5).corr(value.iloc[:, 1])
    actual = correlation(value, value * 2, 5).iloc[:, 0]
    pd.testing.assert_series_equal(actual, direct, check_names=False)
    assert ts_argmax(value, 3).iloc[-1, 0] == 3


def test_restricted_ast_rejects_attributes_and_unknown_calls() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        RestrictedExpression("close.__class__")
    with pytest.raises(ValueError, match="unregistered"):
        RestrictedExpression("eval(close)")


def test_restricted_ast_evaluates_registered_expression() -> None:
    value = _panel()
    result = RestrictedExpression("delta(close, 2) / delay(close, 2)").evaluate({"close": value})
    expected = (value - value.shift(2)) / value.shift(2)
    pd.testing.assert_frame_equal(result, expected)


def test_formula_manifest_counts_and_truthful_statuses(project_root: Path) -> None:
    root = project_root / "src" / "dyadresearch" / "reproductions"
    worldquant = FormulaRegistry.load(root / "worldquant101" / "manifest.yaml")
    gtja = FormulaRegistry.load(root / "gtja_short_cycle" / "manifest.yaml")
    assert len(worldquant.records) == 101
    assert len(gtja.records) == 191
    assert worldquant.status_counts()[FormulaStatus.NOT_IMPLEMENTED.value] > 0
    assert gtja.status_counts()[FormulaStatus.NOT_IMPLEMENTED.value] > 0
    assert worldquant.get("alpha042").delay == 0
    assert worldquant.get("alpha101").source_page == 15
    assert gtja.get("alpha143").source_expression


def test_executable_manifest_formulas_on_synthetic_panel() -> None:
    worldquant = audit_paper("worldquant101")
    gtja = audit_paper("gtja-short-cycle")
    assert worldquant["total"] == 101
    assert gtja["total"] == 191
    assert worldquant["implemented"] > 0
    assert gtja["implemented"] > 0


def test_alpha143_uses_previous_factor_value() -> None:
    close = pd.DataFrame({"A": [10.0, 11.0, 12.1, 10.0]})
    result = alpha143(close)
    assert np.isnan(result.iloc[0, 0])
    assert result.iloc[1, 0] == pytest.approx(0.1)
    assert result.iloc[2, 0] == pytest.approx(0.01)
    assert result.iloc[3, 0] == pytest.approx(0.01)
