from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from dyadresearch.experiments.store import ExperimentStore

WorkflowStatus = Literal["SCHEDULED", "RUNNING", "FINISHED", "FAILED"]

WORKFLOW_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_name TEXT NOT NULL,
    recorder_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('SCHEDULED', 'RUNNING', 'FINISHED', 'FAILED')),
    params_json TEXT NOT NULL DEFAULT '{}',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    tags_json TEXT NOT NULL DEFAULT '{}',
    result_experiment_id INTEGER,
    error_type TEXT,
    error_message TEXT,
    started_at TEXT,
    ended_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY(result_experiment_id) REFERENCES experiments(id)
);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_experiment_created
    ON workflow_runs(experiment_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status_created
    ON workflow_runs(status, created_at DESC);

CREATE TABLE IF NOT EXISTS workflow_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY(run_id) REFERENCES workflow_runs(id) ON DELETE CASCADE,
    UNIQUE(run_id, name)
);
"""


@dataclass(frozen=True, slots=True)
class WorkflowArtifact:
    name: str
    path: str
    sha256: str
    size_bytes: int
    created_at: str


@dataclass(frozen=True, slots=True)
class WorkflowRun:
    id: int
    experiment_name: str
    recorder_name: str
    status: WorkflowStatus
    params: dict[str, Any]
    metrics: dict[str, Any]
    tags: dict[str, Any]
    result_experiment_id: int | None
    error_type: str | None
    error_message: str | None
    started_at: str | None
    ended_at: str | None
    created_at: str
    artifacts: tuple[WorkflowArtifact, ...]


class WorkflowStore:
    """Local experiment-run ledger inspired by Qlib's Recorder boundary."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        ExperimentStore(self.path).initialize()
        with self._connect() as connection:
            connection.executescript(WORKFLOW_SCHEMA)

    def start_run(
        self,
        *,
        experiment_name: str,
        recorder_name: str,
        params: Mapping[str, Any] | None = None,
        tags: Mapping[str, Any] | None = None,
    ) -> WorkflowRun:
        experiment = _required_name(experiment_name, "experiment_name")
        recorder = _required_name(recorder_name, "recorder_name")
        self.initialize()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO workflow_runs("
                "experiment_name, recorder_name, status, params_json, tags_json, started_at"
                ") VALUES (?, ?, 'RUNNING', ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
                (experiment, recorder, _json(params or {}), _json(tags or {})),
            )
            if cursor.lastrowid is None:
                raise sqlite3.DatabaseError("workflow run insert did not return an identifier")
            run_id = int(cursor.lastrowid)
        run = self.get(run_id)
        assert run is not None
        return run

    def log_metrics(self, run_id: int, metrics: Mapping[str, Any]) -> WorkflowRun:
        return self._merge_json(run_id, column="metrics_json", values=metrics)

    def set_tags(self, run_id: int, tags: Mapping[str, Any]) -> WorkflowRun:
        return self._merge_json(run_id, column="tags_json", values=tags)

    def finish(self, run_id: int, *, result_experiment_id: int | None = None) -> WorkflowRun:
        return self._transition(
            run_id,
            target="FINISHED",
            result_experiment_id=result_experiment_id,
        )

    def fail(self, run_id: int, error: BaseException) -> WorkflowRun:
        return self._transition(
            run_id,
            target="FAILED",
            error_type=type(error).__name__,
            error_message=str(error)[:2_000],
        )

    def log_artifact(
        self,
        run_id: int,
        *,
        name: str,
        path: Path,
        sha256: str,
        size_bytes: int,
    ) -> WorkflowRun:
        artifact_name = _artifact_name(name)
        if len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256):
            raise ValueError("artifact sha256 must be a lowercase hexadecimal digest")
        if size_bytes < 0:
            raise ValueError("artifact size must be non-negative")
        self._required_running(run_id)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO workflow_artifacts(run_id, name, path, sha256, size_bytes) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(run_id, name) DO UPDATE SET "
                "path=excluded.path, sha256=excluded.sha256, size_bytes=excluded.size_bytes, "
                "created_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now')",
                (run_id, artifact_name, str(path), sha256, size_bytes),
            )
        run = self.get(run_id)
        assert run is not None
        return run

    def get(self, run_id: int) -> WorkflowRun | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(_RUN_SELECT + " WHERE id=?", (run_id,)).fetchone()
            if row is None:
                return None
            artifacts = connection.execute(
                "SELECT name, path, sha256, size_bytes, created_at "
                "FROM workflow_artifacts WHERE run_id=? ORDER BY id",
                (run_id,),
            ).fetchall()
        return _run(row, artifacts)

    def list(
        self,
        *,
        experiment_name: str | None = None,
        status: WorkflowStatus | None = None,
        limit: int = 100,
    ) -> tuple[WorkflowRun, ...]:
        if not 1 <= limit <= 1_000:
            raise ValueError("workflow run limit must be between 1 and 1000")
        self.initialize()
        clauses: list[str] = []
        params: list[object] = []
        if experiment_name is not None:
            clauses.append("experiment_name=?")
            params.append(experiment_name)
        if status is not None:
            clauses.append("status=?")
            params.append(status)
        sql = _RUN_SELECT
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
            artifacts_by_run = {
                int(row[0]): connection.execute(
                    "SELECT name, path, sha256, size_bytes, created_at "
                    "FROM workflow_artifacts WHERE run_id=? ORDER BY id",
                    (int(row[0]),),
                ).fetchall()
                for row in rows
            }
        return tuple(_run(row, artifacts_by_run[int(row[0])]) for row in rows)

    def _merge_json(
        self,
        run_id: int,
        *,
        column: Literal["metrics_json", "tags_json"],
        values: Mapping[str, Any],
    ) -> WorkflowRun:
        run = self._required_running(run_id)
        current = run.metrics if column == "metrics_json" else run.tags
        merged = {**current, **dict(values)}
        with self._connect() as connection:
            connection.execute(
                f"UPDATE workflow_runs SET {column}=? WHERE id=?",
                (_json(merged), run_id),
            )
        updated = self.get(run_id)
        assert updated is not None
        return updated

    def _transition(
        self,
        run_id: int,
        *,
        target: Literal["FINISHED", "FAILED"],
        result_experiment_id: int | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> WorkflowRun:
        self._required_running(run_id)
        with self._connect() as connection:
            if result_experiment_id is not None:
                exists = connection.execute(
                    "SELECT 1 FROM experiments WHERE id=?", (result_experiment_id,)
                ).fetchone()
                if exists is None:
                    raise ValueError(f"result experiment does not exist: {result_experiment_id}")
            connection.execute(
                "UPDATE workflow_runs SET status=?, result_experiment_id=?, error_type=?, "
                "error_message=?, ended_at=strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id=?",
                (target, result_experiment_id, error_type, error_message, run_id),
            )
        updated = self.get(run_id)
        assert updated is not None
        return updated

    def _required_running(self, run_id: int) -> WorkflowRun:
        run = self.get(run_id)
        if run is None:
            raise ValueError(f"workflow run does not exist: {run_id}")
        if run.status != "RUNNING":
            raise ValueError(f"workflow run {run_id} is not running: {run.status}")
        return run

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection


class WorkflowRecorder:
    """Context-managed local recorder with content-addressed artifacts."""

    def __init__(
        self,
        store: WorkflowStore,
        *,
        artifact_root: Path,
        experiment_name: str,
        recorder_name: str,
        params: Mapping[str, Any] | None = None,
        tags: Mapping[str, Any] | None = None,
    ) -> None:
        self.store = store
        self.artifact_root = artifact_root
        self.experiment_name = experiment_name
        self.recorder_name = recorder_name
        self.params = dict(params or {})
        self.tags = dict(tags or {})
        self.run: WorkflowRun | None = None

    def __enter__(self) -> WorkflowRecorder:
        if self.run is not None:
            raise RuntimeError("workflow recorder cannot be entered twice")
        self.run = self.store.start_run(
            experiment_name=self.experiment_name,
            recorder_name=self.recorder_name,
            params=self.params,
            tags=self.tags,
        )
        return self

    def __exit__(
        self, exc_type: object, exc: BaseException | None, traceback: object
    ) -> Literal[False]:
        del exc_type, traceback
        if exc is not None:
            if self.run is not None and self.run.status == "RUNNING":
                self.run = self.store.fail(self.run.id, exc)
            return False
        if self.run is not None and self.run.status == "RUNNING":
            self.run = self.store.finish(self.run.id)
        return False

    def log_metrics(self, **metrics: Any) -> WorkflowRun:
        run = self._required_run()
        self.run = self.store.log_metrics(run.id, metrics)
        return self.run

    def set_tags(self, **tags: Any) -> WorkflowRun:
        run = self._required_run()
        self.run = self.store.set_tags(run.id, tags)
        return self.run

    def save_object(self, name: str, value: object) -> WorkflowArtifact:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return self._save_bytes(name, payload)

    def log_artifact(self, source: Path, *, name: str | None = None) -> WorkflowArtifact:
        if not source.is_file() or source.is_symlink():
            raise ValueError("workflow artifact source must be a regular file")
        artifact_name = _artifact_name(name or source.name)
        run = self._required_run()
        target = self._target(run.id, artifact_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return self._register_artifact(run.id, artifact_name, target)

    def finish(self, *, result_experiment_id: int | None = None) -> WorkflowRun:
        run = self._required_run()
        self.run = self.store.finish(run.id, result_experiment_id=result_experiment_id)
        return self.run

    def _save_bytes(self, name: str, payload: bytes) -> WorkflowArtifact:
        artifact_name = _artifact_name(name)
        run = self._required_run()
        target = self._target(run.id, artifact_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(payload)
        temporary.replace(target)
        return self._register_artifact(run.id, artifact_name, target)

    def _register_artifact(self, run_id: int, name: str, target: Path) -> WorkflowArtifact:
        payload = target.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        self.run = self.store.log_artifact(
            run_id,
            name=name,
            path=target,
            sha256=digest,
            size_bytes=len(payload),
        )
        return next(artifact for artifact in self.run.artifacts if artifact.name == name)

    def _target(self, run_id: int, name: str) -> Path:
        return self.artifact_root / f"run-{run_id:08d}" / Path(PurePosixPath(name))

    def _required_run(self) -> WorkflowRun:
        if self.run is None:
            raise RuntimeError("workflow recorder has not started")
        if self.run.status != "RUNNING":
            raise RuntimeError(f"workflow recorder is no longer running: {self.run.status}")
        return self.run


_RUN_SELECT = (
    "SELECT id, experiment_name, recorder_name, status, params_json, metrics_json, tags_json, "
    "result_experiment_id, error_type, error_message, started_at, ended_at, created_at "
    "FROM workflow_runs"
)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _required_name(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 128:
        raise ValueError(f"{field} must contain between 1 and 128 characters")
    return normalized


def _artifact_name(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts or path.name in {"", "."}:
        raise ValueError("artifact name must be a safe relative path")
    return path.as_posix()


def _run(row: tuple[Any, ...], artifact_rows: list[tuple[Any, ...]]) -> WorkflowRun:
    return WorkflowRun(
        id=int(row[0]),
        experiment_name=str(row[1]),
        recorder_name=str(row[2]),
        status=str(row[3]),  # type: ignore[arg-type]
        params=json.loads(str(row[4])),
        metrics=json.loads(str(row[5])),
        tags=json.loads(str(row[6])),
        result_experiment_id=None if row[7] is None else int(row[7]),
        error_type=None if row[8] is None else str(row[8]),
        error_message=None if row[9] is None else str(row[9]),
        started_at=None if row[10] is None else str(row[10]),
        ended_at=None if row[11] is None else str(row[11]),
        created_at=str(row[12]),
        artifacts=tuple(
            WorkflowArtifact(
                name=str(artifact[0]),
                path=str(artifact[1]),
                sha256=str(artifact[2]),
                size_bytes=int(artifact[3]),
                created_at=str(artifact[4]),
            )
            for artifact in artifact_rows
        ),
    )
