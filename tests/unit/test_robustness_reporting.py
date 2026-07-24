import json
from pathlib import Path

import pytest

from dyadresearch.experiments.compare import compare_experiments
from dyadresearch.experiments.robustness import (
    grid_search,
    monte_carlo_compounded_returns,
    walk_forward_splits,
)
from dyadresearch.experiments.store import ExperimentRecord
from dyadresearch.reporting.builder import ReportBuilder


def record(identifier: int, value: float) -> ExperimentRecord:
    return ExperimentRecord(
        identifier,
        "backtest",
        f"run-{identifier}",
        f"hash-{identifier}",
        "data",
        {},
        {"metrics": {"return": value}},
        "2026-07-18T00:00:00Z",
    )


def test_walk_forward_has_no_train_test_overlap() -> None:
    splits = walk_forward_splits(100, train_size=60, test_size=20, step=20)
    assert splits[0].train_end == splits[0].test_start
    assert splits == (
        splits[0],
        splits[1],
    )
    with pytest.raises(ValueError, match="positive"):
        walk_forward_splits(10, train_size=0, test_size=2)


def test_monte_carlo_and_grid_search_are_deterministic() -> None:
    first = monte_carlo_compounded_returns([0.1, -0.05, 0.02], simulations=100, seed=7)
    second = monte_carlo_compounded_returns([0.1, -0.05, 0.02], simulations=100, seed=7)
    assert first == second
    ranked = grid_search(
        {"slow": [10, 20], "fast": [2, 5]},
        lambda params: float(params["slow"] - params["fast"]),
    )
    assert ranked[0][0] == {"fast": 2, "slow": 20}


def test_compare_and_static_report(tmp_path: Path) -> None:
    comparison = compare_experiments(record(1, 0.1), record(2, 0.2))
    assert comparison["metric_deltas_right_minus_left"] == {"return": 0.1}
    artifacts = ReportBuilder().build(record(1, 0.1), tmp_path)
    assert Path(artifacts.html).read_text(encoding="utf-8").startswith("<!doctype html>")
    payload = json.loads(Path(artifacts.json).read_text(encoding="utf-8"))
    assert payload["id"] == 1
    assert "metric,value" in Path(artifacts.csv).read_text(encoding="utf-8-sig")
