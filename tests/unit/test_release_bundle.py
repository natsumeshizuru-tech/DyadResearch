from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from dyadresearch.contracts import REQUIRED_BUNDLE_FILES, export_release_bundle, validate_manifest


def valid_manifest() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "strategy_id": "example_momentum",
        "strategy_version": "0.1.0",
        "source_commit": "a" * 40,
        "source_hash": "1" * 64,
        "created_at": "2026-07-19T22:00:00+08:00",
        "research_engine_version": "0.1.0",
        "runtime_api_version": "1.0",
        "strategy_mode": "declarative",
        "parameters": {"lookback": 20},
        "required_data_capabilities": ["bars.1d.none"],
        "allowed_markets": ["SH", "SZ"],
        "allowed_periods": ["1d"],
        "universe_policy": {"point_in_time": True},
        "default_risk_budget": {
            "max_position_weight": 0.2,
            "max_gross_exposure": 1.0,
            "max_daily_turnover": 1.0,
            "max_order_notional": 200000.0,
        },
        "backtest_evidence": {
            "result_id": "example-result",
            "result_hash": "2" * 64,
            "data_fingerprint": "3" * 64,
            "engine_policy": "strict_research",
            "start": "2024-01-01",
            "end": "2026-07-17",
        },
        "limitations": ["Synthetic example only."],
        "approval_status": "candidate",
    }


def valid_artifacts() -> dict[str, object]:
    return {
        "parameters.schema.json": {"type": "object"},
        "required_data.json": {"capabilities": ["bars.1d.none"]},
        "factors.json": [],
        "risk_budget.json": {
            "max_position_weight": 0.2,
            "max_gross_exposure": 1.0,
            "max_daily_turnover": 1.0,
            "max_order_notional": 200000.0,
        },
        "backtest_summary.json": {
            "result_id": "example-result",
            "result_hash": "2" * 64,
            "data_fingerprint": "3" * 64,
            "engine_policy": "strict_research",
            "start": "2024-01-01",
            "end": "2026-07-17",
        },
        "robustness_summary.json": {"status": "not_run"},
        "data_manifest.json": {"classification": "SYNTHETIC", "data_fingerprint": "3" * 64},
        "limitations.md": "# Limitations\n\nSynthetic example only.\n",
        "LICENSES.json": {"project": "Apache-2.0"},
        "signature.json": {"status": "unsigned", "algorithm": "none"},
    }


def test_manifest_schema_rejects_non_pit_universe() -> None:
    manifest = valid_manifest()
    manifest["universe_policy"] = {"point_in_time": False}
    with pytest.raises(ValueError, match="point_in_time"):
        validate_manifest(manifest)


def test_export_writes_complete_verified_checksum_set(tmp_path: Path) -> None:
    destination = tmp_path / "bundle"
    result = export_release_bundle(destination, valid_manifest(), valid_artifacts())
    assert set(result.files) == REQUIRED_BUNDLE_FILES
    checksum_lines = (destination / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    assert len(checksum_lines) == len(REQUIRED_BUNDLE_FILES) - 1
    for line in checksum_lines:
        expected, name = line.split("  ", 1)
        assert hashlib.sha256((destination / name).read_bytes()).hexdigest() == expected
    assert (
        json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["strategy_id"]
        == "example_momentum"
    )


def test_export_rejects_path_artifact(tmp_path: Path) -> None:
    artifacts = valid_artifacts()
    artifacts["../strategy.py"] = "pass\n"
    with pytest.raises(ValueError, match="unsupported bundle artifacts"):
        export_release_bundle(tmp_path / "bundle", valid_manifest(), artifacts)


def test_export_rejects_sidecar_that_disagrees_with_manifest(tmp_path: Path) -> None:
    artifacts = valid_artifacts()
    artifacts["required_data.json"] = {"capabilities": ["bars.1m.none"]}

    with pytest.raises(ValueError, match=r"required_data\.json"):
        export_release_bundle(tmp_path / "bundle", valid_manifest(), artifacts)
