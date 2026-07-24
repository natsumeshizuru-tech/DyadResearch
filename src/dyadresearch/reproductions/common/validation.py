from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from dyadresearch.reproductions.common.metadata import FormulaStatus
from dyadresearch.reproductions.common.registry import FormulaRegistry


@dataclass(frozen=True, slots=True)
class ManifestValidation:
    paper_id: str
    total: int
    implemented: int
    status_counts: dict[str, int]
    manifest_hash: str
    result_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "total": self.total,
            "implemented": self.implemented,
            "status_counts": self.status_counts,
            "manifest_hash": self.manifest_hash,
            "result_hash": self.result_hash,
        }


def validate_manifest(paper_id: str, registry: FormulaRegistry) -> ManifestValidation:
    counts = registry.status_counts()
    unavailable = counts[FormulaStatus.UNAVAILABLE_DEPENDENCY.value]
    not_implemented = counts[FormulaStatus.NOT_IMPLEMENTED.value]
    total = len(registry.records)
    implemented = total - unavailable - not_implemented
    manifest_hash = registry.manifest_hash()
    payload = {
        "paper_id": paper_id,
        "total": total,
        "implemented": implemented,
        "status_counts": counts,
        "manifest_hash": manifest_hash,
    }
    result_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return ManifestValidation(
        paper_id=paper_id,
        total=total,
        implemented=implemented,
        status_counts=counts,
        manifest_hash=manifest_hash,
        result_hash=result_hash,
    )
