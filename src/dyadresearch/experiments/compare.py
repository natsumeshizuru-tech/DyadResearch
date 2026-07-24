from __future__ import annotations

from typing import Any

from dyadresearch.experiments.store import ExperimentRecord


def compare_experiments(left: ExperimentRecord, right: ExperimentRecord) -> dict[str, Any]:
    left_metrics = _metrics(left.result)
    right_metrics = _metrics(right.result)
    keys = sorted(set(left_metrics) | set(right_metrics))
    deltas: dict[str, float | None] = {}
    for key in keys:
        left_value = left_metrics.get(key)
        right_value = right_metrics.get(key)
        deltas[key] = (
            None if left_value is None or right_value is None else right_value - left_value
        )
    return {
        "left_id": left.id,
        "right_id": right.id,
        "same_kind": left.kind == right.kind,
        "same_data": left.data_fingerprint == right.data_fingerprint,
        "same_result": left.result_hash == right.result_hash,
        "metric_deltas_right_minus_left": deltas,
    }


def _metrics(result: dict[str, Any]) -> dict[str, float]:
    candidate = result.get("metrics", result.get("summary", {}))
    if not isinstance(candidate, dict):
        return {}
    return {
        str(key): float(value) for key, value in candidate.items() if isinstance(value, int | float)
    }
