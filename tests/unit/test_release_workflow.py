from __future__ import annotations

import json
from pathlib import Path

import pytest

from dyadresearch.experiments.definitions import DefinitionStore
from dyadresearch.experiments.store import ExperimentStore
from dyadresearch.releases import ReleaseOptions, export_experiment_release, release_receipt


def test_backtest_experiment_exports_complete_strategy_release(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    definition = DefinitionStore(database).get("strategy", "buy_and_hold")
    record = ExperimentStore(database).save(
        kind="backtest",
        name="buy_and_hold",
        result_hash="2" * 64,
        data_fingerprint="3" * 64,
        config={"period": "1d", "policy": "strict_research", "start": 20240102, "end": 20241231},
        result={"metrics": {"total_return": 0.12, "max_drawdown": -0.05}},
    )

    result = export_experiment_release(
        tmp_path / "release",
        record,
        definition,
        ReleaseOptions(),
    )
    receipt = release_receipt(result)
    manifest = json.loads((result.path / "manifest.json").read_text(encoding="utf-8"))

    assert receipt["strategy_id"] == "buy_and_hold"
    assert receipt["approval_status"] == "draft"
    assert manifest["backtest_evidence"]["result_hash"] == record.result_hash
    assert manifest["backtest_evidence"]["start"] == "2024-01-02"
    assert manifest["required_data_capabilities"] == ["bars.1d.none"]
    assert set(result.files) == {
        "LICENSES.json",
        "backtest_summary.json",
        "checksums.sha256",
        "data_manifest.json",
        "factors.json",
        "limitations.md",
        "manifest.json",
        "parameters.schema.json",
        "required_data.json",
        "risk_budget.json",
        "robustness_summary.json",
        "signature.json",
    }


def test_factor_experiment_cannot_be_released_to_trading(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    definition = DefinitionStore(database).get("strategy", "buy_and_hold")
    record = ExperimentStore(database).save(
        kind="factor",
        name="momentum_20",
        result_hash="2" * 64,
        data_fingerprint="3" * 64,
        config={"period": "1d", "start": 20240102, "end": 20241231},
        result={},
    )

    with pytest.raises(ValueError, match="only backtest"):
        export_experiment_release(tmp_path / "release", record, definition, ReleaseOptions())
