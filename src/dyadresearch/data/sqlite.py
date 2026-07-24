from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from dyadresearch.errors import DataContractError


@contextmanager
def readonly_connection(
    path: Path, *, busy_timeout_ms: int = 60_000, immutable: bool = False
) -> Iterator[sqlite3.Connection]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    immutable_query = "&immutable=1" if immutable else ""
    connection = sqlite3.connect(
        f"file:///{resolved.as_posix()}?mode=ro{immutable_query}",
        uri=True,
        timeout=busy_timeout_ms / 1000,
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        connection.execute("PRAGMA temp_store=MEMORY")
        yield connection
    finally:
        connection.close()


def require_columns(connection: sqlite3.Connection, table: str, expected: set[str]) -> None:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if exists is None:
        raise DataContractError(f"missing required table: {table}")
    actual = {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
    missing = expected - actual
    if missing:
        raise DataContractError(f"{table} is missing columns: {sorted(missing)}")
