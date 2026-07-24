from pathlib import Path

import pytest

from dyadresearch.experiments.store import ExperimentStore
from dyadresearch.experiments.workflow import WorkflowRecorder, WorkflowStore


def test_workflow_recorder_tracks_lifecycle_metrics_tags_and_artifacts(tmp_path: Path) -> None:
    database = tmp_path / "research.db"
    experiment = ExperimentStore(database).save(
        kind="factor",
        name="momentum_20",
        result_hash="result-hash",
        data_fingerprint="data-hash",
        config={"lookback": 20},
        result={"coverage_ratio": 1.0},
    )
    store = WorkflowStore(database)

    with WorkflowRecorder(
        store,
        artifact_root=tmp_path / "artifacts",
        experiment_name="factor-research",
        recorder_name="momentum_20",
        params={"lookback": 20},
        tags={"source": "test"},
    ) as recorder:
        recorder.log_metrics(coverage_ratio=1.0, observations=42)
        recorder.set_tags(data_fingerprint="data-hash")
        artifact = recorder.save_object("results/summary.json", {"ok": True})
        finished = recorder.finish(result_experiment_id=experiment.id)

    assert finished.status == "FINISHED"
    assert finished.result_experiment_id == experiment.id
    assert finished.metrics == {"coverage_ratio": 1.0, "observations": 42}
    assert finished.tags == {"source": "test", "data_fingerprint": "data-hash"}
    assert artifact.sha256 == "4062edaf750fb8074e7e83e0c9028c94e32468a8b6f1614774328ef045150f93"
    assert Path(artifact.path).read_text(encoding="utf-8") == '{"ok":true}'
    assert store.list(experiment_name="factor-research") == (store.get(finished.id),)


def test_workflow_recorder_marks_failures_and_rejects_unsafe_artifacts(tmp_path: Path) -> None:
    store = WorkflowStore(tmp_path / "research.db")
    recorder = WorkflowRecorder(
        store,
        artifact_root=tmp_path / "artifacts",
        experiment_name="backtest-research",
        recorder_name="broken-run",
    )

    with pytest.raises(RuntimeError, match="boom"), recorder:
        with pytest.raises(ValueError, match="safe relative"):
            recorder.save_object("../escape.json", {})
        raise RuntimeError("boom")

    assert recorder.run is not None
    assert recorder.run.status == "FAILED"
    assert recorder.run.error_type == "RuntimeError"
    assert recorder.run.error_message == "boom"
    with pytest.raises(ValueError, match="not running"):
        store.log_metrics(recorder.run.id, {"late": 1})
