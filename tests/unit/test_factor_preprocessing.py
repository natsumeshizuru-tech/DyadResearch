from decimal import Decimal

import pytest

from dyadresearch.factors.preprocessing import preprocess_factor_result
from dyadresearch.factors.spec import FactorObservation, FactorResult


def test_preprocessing_winsorizes_standardizes_and_tracks_direction() -> None:
    result = FactorResult(
        name="sample",
        version="1",
        data_fingerprint="data",
        result_hash="raw",
        observations=tuple(
            FactorObservation("000001.SZ", index, 20240100 + index, Decimal(value))
            for index, value in enumerate(("1", "2", "3", "100"), start=1)
        ),
        coverage_ratio=1.0,
        summary={},
    )

    processed = preprocess_factor_result(
        result,
        winsorize=True,
        winsorize_limits=0.25,
        standardize=True,
        direction="low",
    )

    values = [float(item.value) for item in processed.observations]
    assert sum(values) == pytest.approx(0)
    assert processed.summary["mean"] == pytest.approx(0)
    assert processed.result_hash != result.result_hash
