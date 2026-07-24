from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from dyadresearch.reproductions.common.metadata import FormulaRecord, FormulaStatus

EXPECTED_COUNTS = {"worldquant101": 101, "gtja_short_cycle": 191}


class FormulaRegistry:
    def __init__(self, records: tuple[FormulaRecord, ...], *, version: str) -> None:
        self.records = records
        self.version = version
        self._by_id = {record.factor_id: record for record in records}
        if len(self._by_id) != len(records):
            raise ValueError("formula manifest contains duplicate factor_id values")

    @classmethod
    def load(cls, path: Path) -> FormulaRegistry:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("factors"), list):
            raise ValueError(f"invalid formula manifest: {path}")
        paper_id = str(raw.get("paper_id", ""))
        values = raw["factors"]
        records = tuple(FormulaRecord.from_mapping(_mapping(item)) for item in values)
        expected = EXPECTED_COUNTS.get(paper_id)
        if expected is not None and len(records) != expected:
            raise ValueError(f"{paper_id} manifest requires {expected} records, got {len(records)}")
        if any(record.paper_id != paper_id for record in records):
            raise ValueError(f"{paper_id} manifest contains a mismatched paper_id")
        return cls(records, version=str(raw.get("version", "unversioned")))

    def get(self, factor_id: str) -> FormulaRecord:
        try:
            return self._by_id[factor_id]
        except KeyError as exc:
            raise KeyError(f"unknown paper factor: {factor_id}") from exc

    def status_counts(self) -> dict[str, int]:
        counts = {status.value: 0 for status in FormulaStatus}
        for record in self.records:
            counts[record.formula_status.value] += 1
        return counts

    def manifest_hash(self) -> str:
        payload = [
            {
                "factor_id": item.factor_id,
                "source_expression": item.source_expression,
                "normalized_expression": item.normalized_expression,
                "formula_status": item.formula_status.value,
            }
            for item in self.records
        ]
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()


def _mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("formula entries must be mappings")
    return value
