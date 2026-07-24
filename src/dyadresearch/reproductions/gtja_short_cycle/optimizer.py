from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    status: str
    weights: pd.Series
    objective: float | None
    violations: tuple[str, ...]
    solver: str


def construct_long_only_candidate(
    alpha: pd.Series,
    previous: pd.Series,
    *,
    transaction_cost: float = 0.003,
    holdings: int = 50,
    max_weight: float = 0.05,
    max_turnover: float | None = None,
) -> OptimizationResult:
    """Construct and validate a deterministic candidate without hiding solver limits.

    This is a transparent executable candidate, not a claim that the paper's
    undisclosed optimizer has been reproduced.
    """

    clean = alpha.dropna().sort_values(ascending=False).head(holdings)
    if clean.empty or holdings < 1 or not 0 < max_weight <= 1:
        return OptimizationResult("invalid_input", pd.Series(dtype=float), None, (), "candidate")
    shifted = clean - float(clean.min()) + 1e-12
    weights = shifted / float(shifted.sum())
    if float(weights.max()) > max_weight:
        weights = _cap_and_redistribute(weights, max_weight)
    violations: list[str] = []
    if abs(float(weights.sum()) - 1.0) > 1e-8:
        violations.append("fully_invested")
    if (weights < -1e-12).any():
        violations.append("long_only")
    aligned_previous = previous.reindex(weights.index).fillna(0.0)
    turnover = float((weights - aligned_previous).abs().sum())
    if max_turnover is not None and turnover > max_turnover + 1e-8:
        violations.append("max_turnover")
    objective = float((weights * clean).sum() - transaction_cost / 2 * turnover)
    return OptimizationResult(
        "feasible_candidate" if not violations else "constraint_violation",
        weights,
        objective,
        tuple(violations),
        "deterministic_candidate_no_cvxpy",
    )


def _cap_and_redistribute(weights: pd.Series, cap: float) -> pd.Series:
    if len(weights) * cap < 1 - 1e-12:
        return weights * np.nan
    result = weights.copy()
    for _ in range(len(result) + 1):
        over = result > cap
        if not over.any():
            break
        excess = float((result.loc[over] - cap).sum())
        result.loc[over] = cap
        under = ~over
        denominator = float(result.loc[under].sum())
        if denominator <= 0:
            break
        result.loc[under] += result.loc[under] / denominator * excess
    return result / float(result.sum())
