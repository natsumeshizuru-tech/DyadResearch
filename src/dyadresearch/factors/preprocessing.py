from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from decimal import Decimal
from statistics import fmean, pstdev

from dyadresearch.factors.spec import FactorResult


def preprocess_factor_result(
    result: FactorResult,
    *,
    winsorize: bool,
    winsorize_limits: float,
    standardize: bool,
    direction: str,
) -> FactorResult:
    values = [float(item.value) for item in result.observations]
    transformed = list(values)
    if transformed and winsorize:
        lower = _quantile(transformed, winsorize_limits)
        upper = _quantile(transformed, 1 - winsorize_limits)
        transformed = [min(upper, max(lower, value)) for value in transformed]
    if transformed and standardize:
        mean = fmean(transformed)
        deviation = pstdev(transformed)
        transformed = [
            (value - mean) / deviation if deviation > 0 else 0.0 for value in transformed
        ]
    if direction == "low":
        transformed = [-value for value in transformed]
    observations = tuple(
        replace(item, value=Decimal(str(value)))
        for item, value in zip(result.observations, transformed, strict=True)
    )
    summary = {
        "count": float(len(transformed)),
        "mean": fmean(transformed) if transformed else 0.0,
        "minimum": min(transformed) if transformed else 0.0,
        "maximum": max(transformed) if transformed else 0.0,
    }
    settings = {
        "winsorize": winsorize,
        "winsorize_limits": winsorize_limits,
        "standardize": standardize,
        "direction": direction,
    }
    payload = {
        "base_result_hash": result.result_hash,
        "settings": settings,
        "observations": [asdict(item) for item in observations],
    }
    result_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return replace(
        result,
        result_hash=result_hash,
        observations=observations,
        summary=summary,
    )


def _quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight
