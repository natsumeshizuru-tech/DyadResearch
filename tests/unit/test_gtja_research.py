from __future__ import annotations

import numpy as np
import pandas as pd

from dyadresearch.reproductions.gtja_short_cycle.factor_returns import (
    estimate_factor_returns,
)
from dyadresearch.reproductions.gtja_short_cycle.optimizer import (
    construct_long_only_candidate,
)
from dyadresearch.reproductions.gtja_short_cycle.predictor import rolling_alpha_forecast


def test_factor_return_regression_has_no_future_input_leak() -> None:
    dates = pd.RangeIndex(8)
    exposure = pd.DataFrame([[-1.0, 0.0, 1.0]] * len(dates), index=dates, columns=["A", "B", "C"])
    close = pd.DataFrame(
        {
            "A": np.linspace(10, 9, len(dates)),
            "B": np.linspace(10, 10.1, len(dates)),
            "C": np.linspace(10, 12, len(dates)),
        },
        index=dates,
    )
    result = estimate_factor_returns(exposure, close, horizon=1)
    assert result.factor_returns.iloc[0] > 0
    assert np.isnan(result.factor_returns.iloc[-1])


def test_rolling_predictor_shifts_estimation_window() -> None:
    dates = pd.RangeIndex(5)
    exposure = pd.DataFrame(1.0, index=dates, columns=["A", "B"])
    factor_returns = pd.DataFrame({"factor": [1.0, 2.0, 3.0, 4.0, 5.0]}, index=dates)
    result = rolling_alpha_forecast({"factor": exposure}, factor_returns, lookback=2)
    assert np.isnan(result.iloc[1, 0])
    assert result.iloc[2, 0] == 1.5


def test_optimizer_reports_constraint_violation_instead_of_equal_weight_fallback() -> None:
    alpha = pd.Series({"A": 3.0, "B": 2.0, "C": 1.0})
    previous = pd.Series(0.0, index=alpha.index)
    result = construct_long_only_candidate(
        alpha,
        previous,
        holdings=3,
        max_weight=0.5,
        max_turnover=0.1,
    )
    assert result.status == "constraint_violation"
    assert "max_turnover" in result.violations
    assert result.solver == "deterministic_candidate_no_cvxpy"
