from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

REQUIRED_BUNDLE_FILES = frozenset(
    {
        "manifest.json",
        "parameters.schema.json",
        "required_data.json",
        "factors.json",
        "risk_budget.json",
        "backtest_summary.json",
        "robustness_summary.json",
        "data_manifest.json",
        "limitations.md",
        "LICENSES.json",
        "checksums.sha256",
        "signature.json",
    }
)
OPTIONAL_BUNDLE_FILES = frozenset({"strategy.py"})
WRITABLE_ARTIFACTS = (REQUIRED_BUNDLE_FILES | OPTIONAL_BUNDLE_FILES) - {
    "manifest.json",
    "checksums.sha256",
}


@dataclass(frozen=True, slots=True)
class BundleExport:
    path: Path
    bundle_hash: str
    files: tuple[str, ...]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_manifest_schema(path: Path | None = None) -> dict[str, Any]:
    schema_path = path or _project_root() / "contracts" / "strategy-release-bundle.schema.json"
    payload: object = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("strategy release schema must be a JSON object")
    Draft202012Validator.check_schema(payload)
    return payload


def validate_manifest(manifest: Mapping[str, Any], schema_path: Path | None = None) -> None:
    validator = Draft202012Validator(
        load_manifest_schema(schema_path),
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(dict(manifest)), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(
            f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ValueError(f"invalid StrategyReleaseBundle manifest: {details}")


def _artifact_bytes(value: str | bytes | Mapping[str, Any] | list[Any]) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def _validate_artifact_names(artifacts: Mapping[str, object]) -> None:
    names = set(artifacts)
    invalid = names - WRITABLE_ARTIFACTS
    if invalid:
        raise ValueError(f"unsupported bundle artifacts: {sorted(invalid)}")
    missing = WRITABLE_ARTIFACTS - OPTIONAL_BUNDLE_FILES - names
    if missing:
        raise ValueError(f"missing required bundle artifacts: {sorted(missing)}")
    for name in names:
        if Path(name).name != name or "/" in name or "\\" in name:
            raise ValueError(f"bundle artifact must be a plain file name: {name!r}")


def _mapping_artifact(artifacts: Mapping[str, object], name: str) -> Mapping[str, Any]:
    value = artifacts[name]
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a JSON object")
    return value


def _validate_artifact_consistency(
    manifest: Mapping[str, Any], artifacts: Mapping[str, object]
) -> None:
    parameters_schema = dict(_mapping_artifact(artifacts, "parameters.schema.json"))
    Draft202012Validator.check_schema(parameters_schema)
    required_data = _mapping_artifact(artifacts, "required_data.json")
    if required_data.get("capabilities") != manifest["required_data_capabilities"]:
        raise ValueError("required_data.json does not match the manifest")
    if dict(_mapping_artifact(artifacts, "risk_budget.json")) != manifest["default_risk_budget"]:
        raise ValueError("risk_budget.json does not match the manifest")
    evidence = manifest["backtest_evidence"]
    summary = _mapping_artifact(artifacts, "backtest_summary.json")
    for key in ("result_id", "result_hash", "data_fingerprint", "engine_policy", "start", "end"):
        if summary.get(key) != evidence[key]:
            raise ValueError(f"backtest_summary.json does not match the manifest: {key}")
    data_manifest = _mapping_artifact(artifacts, "data_manifest.json")
    if data_manifest.get("data_fingerprint") != evidence["data_fingerprint"]:
        raise ValueError("data_manifest.json does not match the backtest data fingerprint")
    limitations = artifacts["limitations.md"]
    if not isinstance(limitations, str):
        raise ValueError("limitations.md must be text")
    if any(str(item) not in limitations for item in manifest["limitations"]):
        raise ValueError("limitations.md does not cover every manifest limitation")


def export_release_bundle(
    destination: Path,
    manifest: Mapping[str, Any],
    artifacts: Mapping[str, str | bytes | Mapping[str, Any] | list[Any]],
    *,
    schema_path: Path | None = None,
) -> BundleExport:
    """Write a deterministic, checksummed bundle without following arbitrary paths."""

    validate_manifest(manifest, schema_path)
    _validate_artifact_names(artifacts)
    _validate_artifact_consistency(manifest, artifacts)
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        manifest_bytes = (
            json.dumps(dict(manifest), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode()
        payloads = {"manifest.json": manifest_bytes}
        payloads.update({name: _artifact_bytes(value) for name, value in artifacts.items()})
        for name, payload in payloads.items():
            (temporary / name).write_bytes(payload)
        checksum_lines = [
            f"{hashlib.sha256(payload).hexdigest()}  {name}"
            for name, payload in sorted(payloads.items())
        ]
        checksum_bytes = ("\n".join(checksum_lines) + "\n").encode()
        (temporary / "checksums.sha256").write_bytes(checksum_bytes)
        all_files = tuple(sorted({*payloads, "checksums.sha256"}))
        bundle_hash = hashlib.sha256(checksum_bytes).hexdigest()
        os.replace(temporary, destination)
        return BundleExport(path=destination, bundle_hash=bundle_hash, files=all_files)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
