from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


def _load_audit_module():
    script = Path(__file__).parents[2] / "scripts" / "audit_xtdata_2010.py"
    spec = importlib.util.spec_from_file_location("audit_xtdata_2010", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_row_uses_sqlite_column_names() -> None:
    module = _load_audit_module()
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    row = connection.execute("SELECT 7 AS rows, 'stock' AS kind").fetchone()

    assert module._row(row) == {"rows": 7, "kind": "stock"}
