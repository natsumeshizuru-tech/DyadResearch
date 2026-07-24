from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from dyadresearch import __version__
from dyadresearch.contracts import BundleExport, export_release_bundle
from dyadresearch.experiments.definitions import ResearchDefinition
from dyadresearch.experiments.store import ExperimentRecord

ApprovalStatus = Literal[
    "draft",
    "candidate",
    "reviewed",
    "paper_approved",
    "qmt_sim_approved",
    "live_candidate",
    "live_approved",
]


@dataclass(frozen=True, slots=True)
class ReleaseOptions:
    source_commit: str = "UNCOMMITTED"
    runtime_api_version: str = "1.0"
    approval_status: ApprovalStatus = "draft"
    allowed_markets: tuple[str, ...] = ("SH", "SZ")
    limitations: tuple[str, ...] = (
        "Research evidence is historical and does not guarantee future performance.",
    )
    max_position_weight: Decimal = Decimal("0.20")
    max_gross_exposure: Decimal = Decimal("0.80")
    max_daily_turnover: Decimal = Decimal("1.00")
    max_order_notional: Decimal = Decimal("10000")


def export_experiment_release(
    destination: Path,
    record: ExperimentRecord,
    definition: ResearchDefinition,
    options: ReleaseOptions,
) -> BundleExport:
    """Export a backtest experiment as the only supported research-to-trading handoff."""

    if record.kind != "backtest":
        raise ValueError("only backtest experiments can be released to trading")
    if definition.kind != "strategy" or definition.name != record.name:
        raise ValueError("backtest experiment and strategy definition do not match")
    period = str(record.config.get("period", "1d"))
    allowed_periods = {"tick", "1m", "5m", "15m", "30m", "1h", "1d", "1w", "1q", "1y"}
    if period not in allowed_periods:
        raise ValueError(f"strategy period is not supported by the runtime contract: {period}")
    source_hash = hashlib.sha256(definition.code.encode("utf-8")).hexdigest()
    required_capabilities = [f"bars.{period}.none"]
    evidence = {
        "result_id": str(record.id),
        "result_hash": record.result_hash,
        "data_fingerprint": record.data_fingerprint,
        "engine_policy": str(record.config.get("policy", "strict_research")),
        "start": _iso_date(record.config.get("start")),
        "end": _iso_date(record.config.get("end")),
    }
    risk_budget = {
        "max_position_weight": float(options.max_position_weight),
        "max_gross_exposure": float(options.max_gross_exposure),
        "max_daily_turnover": float(options.max_daily_turnover),
        "max_order_notional": float(options.max_order_notional),
    }
    parameters = definition.config.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ValueError("strategy parameters must be an object")
    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "strategy_id": definition.name,
        "strategy_version": f"0.1.{definition.version}",
        "source_commit": options.source_commit,
        "source_hash": source_hash,
        "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "research_engine_version": __version__,
        "runtime_api_version": options.runtime_api_version,
        "strategy_mode": "preinstalled_plugin",
        "parameters": parameters,
        "required_data_capabilities": required_capabilities,
        "allowed_markets": list(options.allowed_markets),
        "allowed_periods": [period],
        "universe_policy": {"point_in_time": True},
        "default_risk_budget": risk_budget,
        "backtest_evidence": evidence,
        "limitations": list(options.limitations),
        "approval_status": options.approval_status,
    }
    artifacts: dict[str, Any] = {
        "parameters.schema.json": _parameter_schema(parameters),
        "required_data.json": {"capabilities": required_capabilities},
        "factors.json": [],
        "risk_budget.json": risk_budget,
        "backtest_summary.json": {
            **evidence,
            "metrics": record.result.get("metrics", {}),
            "strategy": definition.name,
        },
        "robustness_summary.json": record.result.get(
            "robustness", {"status": "not_run", "limitations": list(options.limitations)}
        ),
        "data_manifest.json": {
            "data_fingerprint": record.data_fingerprint,
            "classification": "LOCAL_RESEARCH_DATA",
            "paths_included": False,
        },
        "limitations.md": "# Limitations\n\n"
        + "\n".join(f"- {item}" for item in options.limitations)
        + "\n",
        "LICENSES.json": {"dyadresearch": "Apache-2.0"},
        "signature.json": {"status": "unsigned", "algorithm": "none"},
    }
    return export_release_bundle(destination, manifest, artifacts)


def _iso_date(value: object) -> str:
    text = str(value or "")
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError as exc:
        raise ValueError(f"invalid experiment date: {value!r}") from exc


def _parameter_schema(parameters: dict[str, Any]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for name, value in parameters.items():
        json_type = (
            "boolean"
            if isinstance(value, bool)
            else "integer"
            if isinstance(value, int)
            else "number"
            if isinstance(value, float)
            else "string"
        )
        properties[str(name)] = {"type": json_type, "default": value}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }


def release_receipt(result: BundleExport) -> dict[str, Any]:
    manifest = json.loads((result.path / "manifest.json").read_text(encoding="utf-8"))
    return {
        "path": str(result.path),
        "bundle_hash": result.bundle_hash,
        "files": list(result.files),
        "strategy_id": manifest["strategy_id"],
        "strategy_version": manifest["strategy_version"],
        "approval_status": manifest["approval_status"],
    }
