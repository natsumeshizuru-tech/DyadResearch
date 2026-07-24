from __future__ import annotations

import pandas as pd


def rolling_alpha_forecast(
    exposures: dict[str, pd.DataFrame],
    factor_returns: pd.DataFrame,
    *,
    lookback: int = 250,
) -> pd.DataFrame:
    if lookback < 2:
        raise ValueError("rolling predictor lookback must be at least two")
    missing = sorted(set(exposures) - set(factor_returns.columns))
    if missing:
        raise ValueError(f"factor return history is missing: {missing}")
    means = factor_returns.rolling(lookback, min_periods=lookback).mean().shift(1)
    first = next(iter(exposures.values()))
    forecast = first.copy() * 0.0
    for name, exposure in exposures.items():
        forecast = forecast + exposure.mul(means[name], axis=0)
    return forecast.where(first.notna())
