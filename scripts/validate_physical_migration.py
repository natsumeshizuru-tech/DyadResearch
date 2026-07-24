from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class DatabaseValidation:
    name: str
    source_bytes: int
    target_bytes: int
    source_sha256: str
    target_sha256: str
    hash_equal: bool
    integrity: str
    rows: dict[str, int]
    date_bounds: dict[str, int | None]
    duplicate_primary_keys: dict[str, bool]
    seconds: float


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb", buffering=0) as handle:
        buffer = bytearray(8 * 1024 * 1024)
        view = memoryview(buffer)
        while size := handle.readinto(buffer):
            digest.update(view[:size])
    return digest.hexdigest()


def validate_database(source: Path, target: Path) -> DatabaseValidation:
    started = time.perf_counter()
    source_hash = sha256(source)
    target_hash = sha256(target)
    with sqlite3.connect(f"file:///{target.resolve().as_posix()}?mode=ro", uri=True) as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        rows = {table: _count(connection, table) for table in tables}
        date_bounds = _date_bounds(connection, tables)
        duplicates = {
            table: _has_duplicate_primary_key(connection, table)
            for table in tables
            if _primary_key_columns(connection, table)
        }
    return DatabaseValidation(
        name=source.name,
        source_bytes=source.stat().st_size,
        target_bytes=target.stat().st_size,
        source_sha256=source_hash,
        target_sha256=target_hash,
        hash_equal=source_hash == target_hash,
        integrity=integrity,
        rows=rows,
        date_bounds=date_bounds,
        duplicate_primary_keys=duplicates,
        seconds=round(time.perf_counter() - started, 3),
    )


def _count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])


def _date_bounds(connection: sqlite3.Connection, tables: list[str]) -> dict[str, int | None]:
    if "bars" in tables:
        row = connection.execute("SELECT min(trade_date), max(trade_date) FROM bars").fetchone()
        return {"first_trade_date": _optional_int(row[0]), "last_trade_date": _optional_int(row[1])}
    if "financial_records" in tables:
        row = connection.execute(
            "SELECT min(NULLIF(report_date, 0)), max(NULLIF(report_date, 0)), "
            "max(NULLIF(announcement_date, 0)) FROM financial_records"
        ).fetchone()
        return {
            "first_report_date": _optional_int(row[0]),
            "last_report_date": _optional_int(row[1]),
            "last_announcement_date": _optional_int(row[2]),
        }
    return {}


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _primary_key_columns(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    columns = sorted(
        (
            (int(row[5]), str(row[1]))
            for row in connection.execute(f'PRAGMA table_info("{table}")')
            if int(row[5]) > 0
        ),
        key=lambda item: item[0],
    )
    return tuple(name for _, name in columns)


def _has_duplicate_primary_key(connection: sqlite3.Connection, table: str) -> bool:
    columns = _primary_key_columns(connection, table)
    quoted = ", ".join(f'"{column}"' for column in columns)
    row = connection.execute(
        f'SELECT 1 FROM "{table}" GROUP BY {quoted} HAVING count(*) > 1 LIMIT 1'
    ).fetchone()
    return row is not None


def validate(source_root: Path, target_root: Path, workers: int) -> dict[str, Any]:
    source_files = {path.name: path for path in source_root.glob("*.db")}
    target_files = {path.name: path for path in target_root.glob("*.db")}
    missing = sorted(set(source_files) - set(target_files))
    extras = sorted(set(target_files) - set(source_files))
    results: list[DatabaseValidation] = []
    names = sorted(set(source_files) & set(target_files))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(validate_database, source_files[name], target_files[name]): name
            for name in names
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                f"validated {result.name}: hash={result.hash_equal} "
                f"integrity={result.integrity} seconds={result.seconds}",
                flush=True,
            )
    results.sort(key=lambda item: item.name)
    accepted = (
        not missing
        and not extras
        and all(item.hash_equal for item in results)
        and all(item.integrity == "ok" for item in results)
        and not any(
            duplicate for item in results for duplicate in item.duplicate_primary_keys.values()
        )
    )
    return {
        "accepted": accepted,
        "source_root": str(source_root.resolve()),
        "target_root": str(target_root.resolve()),
        "database_count": len(results),
        "missing": missing,
        "extras": extras,
        "source_bytes": sum(item.source_bytes for item in results),
        "target_bytes": sum(item.target_bytes for item in results),
        "all_hashes_equal": all(item.hash_equal for item in results),
        "all_integrity_ok": all(item.integrity == "ok" for item in results),
        "duplicate_primary_keys": sum(
            int(duplicate) for item in results for duplicate in item.duplicate_primary_keys.values()
        ),
        "databases": [asdict(item) for item in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    payload = validate(args.source, args.target, args.workers)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "databases"}))
    return 0 if payload["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
