from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

Panel = pd.DataFrame


def _window(value: int | float) -> int:
    result = math.floor(float(value))
    if result < 1:
        raise ValueError("rolling window must floor to a positive integer")
    return result


def finite(value: Panel) -> Panel:
    return value.replace([np.inf, -np.inf], np.nan)


def rank(value: Panel, *, minimum_sample: int = 2) -> Panel:
    ranked = value.rank(axis=1, method="average", pct=True, na_option="keep")
    counts = value.notna().sum(axis=1)
    return ranked.where(counts >= minimum_sample, np.nan)


def standardize(value: Panel) -> Panel:
    mean_value = value.mean(axis=1)
    std_value = value.std(axis=1, ddof=0).replace(0, np.nan)
    return finite(value.sub(mean_value, axis=0).div(std_value, axis=0))


def winsorize(value: Panel, *, lower: float = 0.01, upper: float = 0.99) -> Panel:
    if not 0 <= lower < upper <= 1:
        raise ValueError("winsorization bounds must satisfy 0 <= lower < upper <= 1")
    low = value.quantile(lower, axis=1)
    high = value.quantile(upper, axis=1)
    return value.clip(lower=low, upper=high, axis=0)


def industry_demean(value: Panel, industries: Panel) -> Panel:
    if not value.index.equals(industries.index) or not value.columns.equals(industries.columns):
        raise ValueError("industry labels must align with the factor panel")
    output = value.copy()
    for date in value.index:
        row = value.loc[date]
        labels = industries.loc[date]
        output.loc[date] = row - row.groupby(labels).transform("mean")
    return output


def style_residualize(value: Panel, exposures: dict[str, Panel]) -> Panel:
    output = value.copy() * np.nan
    for date in value.index:
        y = value.loc[date]
        columns = [panel.loc[date].rename(name) for name, panel in exposures.items()]
        if not columns:
            output.loc[date] = y
            continue
        x = pd.concat(columns, axis=1)
        valid = y.notna() & x.notna().all(axis=1)
        if int(valid.sum()) <= x.shape[1]:
            continue
        design = np.column_stack((np.ones(int(valid.sum())), x.loc[valid].to_numpy(float)))
        coefficients = np.linalg.lstsq(design, y.loc[valid].to_numpy(float), rcond=None)[0]
        output.loc[date, valid] = y.loc[valid] - design @ coefficients
    return output


def delay(value: Panel, periods: int | float = 1) -> Panel:
    return value.shift(_window(periods))


def delta(value: Panel, periods: int | float = 1) -> Panel:
    return value - delay(value, periods)


def ts_sum(value: Panel, window: int | float) -> Panel:
    size = _window(window)
    return value.rolling(size, min_periods=size).sum()


def mean(value: Panel, window: int | float) -> Panel:
    size = _window(window)
    return value.rolling(size, min_periods=size).mean()


def stddev(value: Panel, window: int | float) -> Panel:
    size = _window(window)
    return value.rolling(size, min_periods=size).std(ddof=0)


def correlation(left: Panel, right: Panel, window: int | float) -> Panel:
    size = _window(window)
    return finite(left.rolling(size, min_periods=size).corr(right))


def covariance(left: Panel, right: Panel, window: int | float) -> Panel:
    size = _window(window)
    return finite(left.rolling(size, min_periods=size).cov(right, ddof=0))


def ts_min(value: Panel, window: int | float) -> Panel:
    size = _window(window)
    return value.rolling(size, min_periods=size).min()


def ts_max(value: Panel, window: int | float) -> Panel:
    size = _window(window)
    return value.rolling(size, min_periods=size).max()


def ts_argmin(value: Panel, window: int | float) -> Panel:
    size = _window(window)
    return value.rolling(size, min_periods=size).apply(lambda row: float(np.argmin(row)) + 1)


def ts_argmax(value: Panel, window: int | float) -> Panel:
    size = _window(window)
    return value.rolling(size, min_periods=size).apply(lambda row: float(np.argmax(row)) + 1)


def ts_rank(value: Panel, window: int | float) -> Panel:
    size = _window(window)

    def last_rank(row: np.ndarray[Any, np.dtype[np.float64]]) -> float:
        if np.isnan(row[-1]):
            return np.nan
        return float(pd.Series(row).rank(method="average", pct=True).iloc[-1])

    return value.rolling(size, min_periods=size).apply(last_rank, raw=True)


def product(value: Panel, window: int | float) -> Panel:
    size = _window(window)
    return value.rolling(size, min_periods=size).apply(np.prod, raw=True)


def signed_power(value: Panel, exponent: float) -> Panel:
    return pd.DataFrame(
        np.sign(value.to_numpy(float)) * np.power(np.abs(value.to_numpy(float)), exponent),
        index=value.index,
        columns=value.columns,
    )


def scale(value: Panel, constant: float = 1.0) -> Panel:
    denominator = value.abs().sum(axis=1).replace(0, np.nan)
    return finite(value.div(denominator, axis=0) * constant)


def decay_linear(value: Panel, window: int | float) -> Panel:
    size = _window(window)
    weights = np.arange(1, size + 1, dtype=float)
    weights /= weights.sum()
    return value.rolling(size, min_periods=size).apply(
        lambda row: float(np.dot(row, weights)), raw=True
    )


def where(condition: Panel, when_true: Panel | float, when_false: Panel | float) -> Panel:
    return pd.DataFrame(
        np.where(condition, when_true, when_false),
        index=condition.index,
        columns=condition.columns,
    )


def sma(value: Panel, window: int | float, weight: int | float) -> Panel:
    size = _window(window)
    numerator = float(weight)
    if not 0 < numerator <= size:
        raise ValueError("SMA weight must be in (0, window]")
    alpha = numerator / size
    return value.ewm(alpha=alpha, adjust=False, min_periods=size).mean()


def wma(value: Panel, window: int | float) -> Panel:
    return decay_linear(value, window)


def count(condition: Panel, window: int | float) -> Panel:
    return ts_sum(condition.astype(float), window)


def sumif(value: Panel, condition: Panel, window: int | float) -> Panel:
    return ts_sum(value.where(condition, 0.0), window)


def sequence(window: int | float, columns: Sequence[str] = ("sequence",)) -> Panel:
    size = _window(window)
    return pd.DataFrame(
        np.tile(np.arange(1, size + 1, dtype=float)[:, None], (1, len(columns))),
        columns=list(columns),
    )


def regbeta(y: Panel, x: Panel, window: int | float) -> Panel:
    size = _window(window)
    result = y.copy() * np.nan
    for column in y.columns:
        covariance_value = y[column].rolling(size, min_periods=size).cov(x[column], ddof=0)
        variance_value = x[column].rolling(size, min_periods=size).var(ddof=0).replace(0, np.nan)
        result[column] = covariance_value / variance_value
    return finite(result)


def regresi(y: Panel, factors: Sequence[Panel], window: int | float) -> Panel:
    size = _window(window)
    if not factors:
        raise ValueError("REGRESI requires at least one factor")
    output = y.copy() * np.nan
    for column in y.columns:
        for position in range(size - 1, len(y.index)):
            index = y.index[position - size + 1 : position + 1]
            target = y.loc[index, column]
            design = pd.concat([factor.loc[index, column] for factor in factors], axis=1)
            valid = target.notna() & design.notna().all(axis=1)
            if int(valid.sum()) <= design.shape[1]:
                continue
            x = np.column_stack((np.ones(int(valid.sum())), design.loc[valid].to_numpy(float)))
            coefficients = np.linalg.lstsq(x, target.loc[valid].to_numpy(float), rcond=None)[0]
            output.loc[y.index[position], column] = target.loc[valid].iloc[-1] - (
                x[-1] @ coefficients
            )
    return output


def dtm(open_price: Panel, high: Panel) -> Panel:
    previous_open = delay(open_price)
    return where(
        open_price <= previous_open,
        0.0,
        pd.DataFrame(
            np.maximum(high - open_price, open_price - previous_open),
            index=open_price.index,
            columns=open_price.columns,
        ),
    )


def dbm(open_price: Panel, low: Panel) -> Panel:
    previous_open = delay(open_price)
    return where(
        open_price >= previous_open,
        0.0,
        pd.DataFrame(
            np.maximum(open_price - low, previous_open - open_price),
            index=open_price.index,
            columns=open_price.columns,
        ),
    )


def tr(high: Panel, low: Panel, close: Panel) -> Panel:
    previous_close = delay(close)
    return pd.DataFrame(
        np.maximum.reduce(
            [
                (high - low).to_numpy(float),
                (high - previous_close).abs().to_numpy(float),
                (low - previous_close).abs().to_numpy(float),
            ]
        ),
        index=high.index,
        columns=high.columns,
    )


def hd(high: Panel) -> Panel:
    return high - delay(high)


def ld(low: Panel) -> Panel:
    return delay(low) - low


def self_previous(value: Panel) -> Panel:
    return delay(value)


OPERATOR_REGISTRY: dict[str, Any] = {
    "abs": np.abs,
    "correlation": correlation,
    "count": count,
    "covariance": covariance,
    "decay_linear": decay_linear,
    "delay": delay,
    "delta": delta,
    "log": np.log,
    "max": lambda left, right: pd.DataFrame(
        np.maximum(left, right), index=left.index, columns=left.columns
    ),
    "mean": mean,
    "min": lambda left, right: pd.DataFrame(
        np.minimum(left, right), index=left.index, columns=left.columns
    ),
    "product": product,
    "rank": rank,
    "regbeta": regbeta,
    "scale": scale,
    "sign": np.sign,
    "signed_power": signed_power,
    "sma": sma,
    "stddev": stddev,
    "sum": ts_sum,
    "sumif": sumif,
    "ts_argmax": ts_argmax,
    "ts_argmin": ts_argmin,
    "ts_max": ts_max,
    "ts_min": ts_min,
    "ts_rank": ts_rank,
    "where": where,
    "wma": wma,
}
