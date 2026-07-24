from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    result_hash TEXT NOT NULL,
    data_fingerprint TEXT NOT NULL,
    config_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(kind, result_hash)
);
CREATE INDEX IF NOT EXISTS idx_experiments_kind_created
    ON experiments(kind, created_at DESC);
"""


@dataclass(frozen=True, slots=True)
class ExperimentRecord:
    id: int
    kind: str
    name: str
    result_hash: str
    data_fingerprint: str
    config: dict[str, Any]
    result: dict[str, Any]
    created_at: str


class ExperimentStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.executescript(SCHEMA)

    def save(
        self,
        *,
        kind: str,
        name: str,
        result_hash: str,
        data_fingerprint: str,
        config: dict[str, Any],
        result: dict[str, Any],
    ) -> ExperimentRecord:
        self.initialize()
        config_json = _json(config)
        result_json = _json(result)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                "INSERT INTO experiments(kind, name, result_hash, data_fingerprint, "
                "config_json, result_json) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(kind, result_hash) DO UPDATE SET "
                "name=excluded.name, config_json=excluded.config_json, "
                "result_json=excluded.result_json",
                (kind, name, result_hash, data_fingerprint, config_json, result_json),
            )
            row = connection.execute(
                "SELECT id, kind, name, result_hash, data_fingerprint, config_json, "
                "result_json, created_at FROM experiments WHERE kind=? AND result_hash=?",
                (kind, result_hash),
            ).fetchone()
        assert row is not None
        return _record(row)

    def get(self, experiment_id: int) -> ExperimentRecord | None:
        self.initialize()
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT id, kind, name, result_hash, data_fingerprint, config_json, "
                "result_json, created_at FROM experiments WHERE id=?",
                (experiment_id,),
            ).fetchone()
        return None if row is None else _record(row)

    def list(self, *, kind: str | None = None) -> tuple[ExperimentRecord, ...]:
        self.initialize()
        sql = (
            "SELECT id, kind, name, result_hash, data_fingerprint, config_json, "
            "result_json, created_at FROM experiments"
        )
        params: tuple[str, ...] = ()
        if kind is not None:
            sql += " WHERE kind=?"
            params = (kind,)
        sql += " ORDER BY id"
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(sql, params).fetchall()
        return tuple(_record(row) for row in rows)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _record(row: tuple[Any, ...]) -> ExperimentRecord:
    return ExperimentRecord(
        id=int(row[0]),
        kind=str(row[1]),
        name=str(row[2]),
        result_hash=str(row[3]),
        data_fingerprint=str(row[4]),
        config=json.loads(str(row[5])),
        result=json.loads(str(row[6])),
        created_at=str(row[7]),
    )
