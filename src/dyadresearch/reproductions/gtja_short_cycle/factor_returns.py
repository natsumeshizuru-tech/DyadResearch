from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from dyadresearch.reproductions.common.operators import rank


@dataclass(frozen=True, slots=True)
class FactorReturnResult:
    horizon: int
    factor_returns: pd.Series
    ic: pd.Series
    rank_ic: pd.Series
    coverage: pd.Series


def estimate_factor_returns(
    exposure: pd.DataFrame,
    close: pd.DataFrame,
    *,
    horizon: int,
) -> FactorReturnResult:
    if horizon not in {1, 2, 3, 4, 5}:
        raise ValueError("GTJA factor-return horizon must be 1 through 5")
    forward = close.shift(-horizon) / close - 1
    returns: dict[object, float] = {}
    ic_values: dict[object, float] = {}
    rank_values: dict[object, float] = {}
    coverage: dict[object, float] = {}
    for date in exposure.index:
        x = exposure.loc[date]
        y = forward.loc[date]
        valid = x.notna() & y.notna()
        coverage[date] = float(valid.mean())
        if int(valid.sum()) < 3 or float(x.loc[valid].std(ddof=0)) == 0:
            returns[date] = np.nan
            ic_values[date] = np.nan
            rank_values[date] = np.nan
            continue
        design = np.column_stack((np.ones(int(valid.sum())), x.loc[valid].to_numpy(float)))
        coefficients = np.linalg.lstsq(design, y.loc[valid].to_numpy(float), rcond=None)[0]
        returns[date] = float(coefficients[1])
        ic_values[date] = float(x.loc[valid].corr(y.loc[valid]))
        ranked_x = rank(pd.DataFrame([x.loc[valid]], index=[date])).iloc[0]
        ranked_y = rank(pd.DataFrame([y.loc[valid]], index=[date])).iloc[0]
        rank_values[date] = float(ranked_x.corr(ranked_y))
    return FactorReturnResult(
        horizon=horizon,
        factor_returns=pd.Series(returns, dtype=float),
        ic=pd.Series(ic_values, dtype=float),
        rank_ic=pd.Series(rank_values, dtype=float),
        coverage=pd.Series(coverage, dtype=float),
    )
