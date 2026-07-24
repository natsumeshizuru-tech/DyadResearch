from __future__ import annotations

import hashlib
import html
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from dyadresearch.config import ResearchConfig
from dyadresearch.data.capabilities import capability_matrix
from dyadresearch.experiments.store import ExperimentStore
from dyadresearch.reproductions.common.metadata import FormulaStatus
from dyadresearch.reproductions.common.registry import FormulaRegistry
from dyadresearch.reproductions.common.validation import validate_manifest
from dyadresearch.reproductions.gtja_short_cycle.factors import (
    evaluate_panel_factor as evaluate_gtja,
)
from dyadresearch.reproductions.gtja_short_cycle.factors import (
    load_registry as load_gtja,
)
from dyadresearch.reproductions.worldquant101.factors import (
    evaluate_panel_factor as evaluate_worldquant,
)
from dyadresearch.reproductions.worldquant101.factors import (
    load_registry as load_worldquant,
)

_PROTOCOLS = {
    "worldquant101": {
        "formula-validation": ("wq101_formula_validation", "B"),
        "wq101_formula_validation": ("wq101_formula_validation", "B"),
        "original-market": ("wq101_original_market", "A"),
        "wq101_original_market": ("wq101_original_market", "A"),
        "ashare-transfer": ("wq101_ashare_transfer", "D"),
        "wq101_ashare_transfer": ("wq101_ashare_transfer", "D"),
    },
    "gtja_short_cycle": {
        "paper-strict": ("paper_strict", "A"),
        "paper_strict": ("paper_strict", "A"),
        "transparent-reconstruction": ("transparent_reconstruction", "C"),
        "transparent_reconstruction": ("transparent_reconstruction", "C"),
        "ashare-executable": ("ashare_executable", "D"),
        "ashare_executable": ("ashare_executable", "D"),
    },
}


def audit_paper(paper_id: str) -> dict[str, Any]:
    normalized = _paper_id(paper_id)
    registry = _registry(normalized)
    validation = validate_manifest(normalized, registry).to_dict()
    validation["ambiguity_count"] = sum(bool(item.ambiguity_notes) for item in registry.records)
    validation["delay_zero"] = [item.factor_id for item in registry.records if item.delay == 0]
    return validation


def run_paper_protocol(
    config: ResearchConfig,
    paper_id: str,
    protocol: str,
    *,
    output_root: str | Path,
) -> dict[str, Any]:
    normalized = _paper_id(paper_id)
    try:
        canonical, comparability = _PROTOCOLS[normalized][protocol]
    except KeyError as exc:
        raise ValueError(f"unsupported {normalized} protocol: {protocol}") from exc
    registry = _registry(normalized)
    validation = validate_manifest(normalized, registry).to_dict()
    smoke = _smoke_test(normalized, registry)
    status, blockers = _status(normalized, canonical, validation)
    capabilities = capability_matrix(config.data.root)
    capability_hash = _hash(capabilities)
    result: dict[str, Any] = {
        "schema_version": "1.0.0",
        "paper_id": normalized,
        "protocol": canonical,
        "status": status,
        "comparability_level": comparability,
        "formula_validation": validation,
        "synthetic_smoke": smoke,
        "data_capability_hash": capability_hash,
        "git_commit": _git_commit(),
        "blockers": blockers,
        "claims": _claims(normalized, canonical, status),
    }
    result_hash = _hash(result)
    result["result_hash"] = result_hash
    record = ExperimentStore(config.research.database).save(
        kind="paper_reproduction",
        name=f"{normalized}:{canonical}",
        result_hash=result_hash,
        data_fingerprint=capability_hash,
        config={
            "paper_id": normalized,
            "protocol": canonical,
            "manifest_version": registry.version,
            "manifest_hash": validation["manifest_hash"],
            "comparability_level": comparability,
        },
        result=result,
    )
    artifacts = _write_report(Path(output_root), result, record.id)
    return {
        "ok": status not in {"failed"},
        "experiment_id": record.id,
        "paper_id": normalized,
        "protocol": canonical,
        "status": status,
        "comparability_level": comparability,
        "result_hash": result_hash,
        "artifacts": artifacts,
        "blockers": blockers,
    }


def compare_paper_experiments(
    config: ResearchConfig, left_id: int, right_id: int
) -> dict[str, Any]:
    store = ExperimentStore(config.research.database)
    left = store.get(left_id)
    right = store.get(right_id)
    if left is None or right is None:
        raise ValueError("both paper experiment IDs must exist")
    return {
        "left_id": left.id,
        "right_id": right.id,
        "same_data_fingerprint": left.data_fingerprint == right.data_fingerprint,
        "same_result_hash": left.result_hash == right.result_hash,
        "left": {
            "name": left.name,
            "status": left.result.get("status"),
            "comparability_level": left.result.get("comparability_level"),
        },
        "right": {
            "name": right.name,
            "status": right.result.get("status"),
            "comparability_level": right.result.get("comparability_level"),
        },
    }


def _smoke_test(paper_id: str, registry: FormulaRegistry) -> dict[str, Any]:
    inputs = _synthetic_inputs()
    evaluator = evaluate_worldquant if paper_id == "worldquant101" else evaluate_gtja
    passed: list[str] = []
    failures: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for record in registry.records:
        if record.formula_status not in {
            FormulaStatus.EXACT,
            FormulaStatus.NORMALIZED,
            FormulaStatus.CORRECTED_TYPO,
            FormulaStatus.ASSUMPTION,
        }:
            continue
        try:
            result = evaluator(record.factor_id, inputs)
            if result.shape != inputs["close"].shape:
                raise ValueError(f"shape mismatch: {result.shape}")
            passed.append(record.factor_id)
            values = np.nan_to_num(result.to_numpy(float), nan=0.0, posinf=0.0, neginf=0.0)
            hashes[record.factor_id] = hashlib.sha256(values.tobytes()).hexdigest()
        except (ArithmeticError, KeyError, TypeError, ValueError) as exc:
            failures[record.factor_id] = str(exc)
    return {
        "attempted": len(passed) + len(failures),
        "passed": len(passed),
        "failed": len(failures),
        "passed_factor_ids": passed,
        "failures": failures,
        "output_hash": _hash(hashes),
    }


def _synthetic_inputs() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(20260725)
    dates = pd.RangeIndex(0, 520, name="session")
    symbols = [f"S{index:02d}" for index in range(8)]
    returns = pd.DataFrame(
        rng.normal(0.0003, 0.012, (len(dates), len(symbols))),
        index=dates,
        columns=symbols,
    )
    close = 20.0 * (1.0 + returns).cumprod()
    open_price = (
        close.shift(1)
        .fillna(close.iloc[0])
        .mul(1.0 + pd.DataFrame(rng.normal(0, 0.003, close.shape), index=dates, columns=symbols))
    )
    spread = pd.DataFrame(rng.uniform(0.002, 0.025, close.shape), index=dates, columns=symbols)
    high = pd.DataFrame(np.maximum(open_price, close) * (1 + spread), index=dates, columns=symbols)
    low = pd.DataFrame(np.minimum(open_price, close) * (1 - spread), index=dates, columns=symbols)
    volume = pd.DataFrame(rng.lognormal(13.0, 0.45, close.shape), index=dates, columns=symbols)
    vwap = (open_price + high + low + close) / 4
    amount = vwap * volume
    cap = close * pd.DataFrame(rng.uniform(1e8, 8e8, close.shape), index=dates, columns=symbols)
    return {
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "vwap": vwap,
        "amount": amount,
        "returns": returns,
        "cap": cap,
        "self_previous": close.copy() * 0 + 1.0,
    }


def _status(paper_id: str, protocol: str, validation: dict[str, Any]) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if validation["implemented"] < validation["total"]:
        blockers.append(
            f"formula implementation coverage is {validation['implemented']}/{validation['total']}"
        )
    if protocol == "wq101_original_market":
        blockers.append(
            "equivalent proprietary WorldQuant US universe, classifications and "
            "realized alpha-return data are unavailable"
        )
        return "not_run", blockers
    if protocol == "wq101_ashare_transfer":
        blockers.append("full formula coverage and historical industry snapshots are unavailable")
        return "not_run", blockers
    if protocol == "paper_strict":
        blockers.extend(
            [
                "historical industry snapshots are unavailable",
                "historical CSI 500 weights are unavailable",
                "consensus fields EPIBS, EGIB and EGIB_S are unavailable",
            ]
        )
        return "not_run", blockers
    if protocol == "ashare_executable":
        blockers.append("no full 191-factor target portfolio has been produced")
    return ("validated" if not blockers else "partial"), blockers


def _claims(paper_id: str, protocol: str, status: str) -> list[str]:
    claims = ["Formula records retain source expressions and explicit implementation status."]
    if paper_id == "worldquant101":
        claims.append("Local A-share evidence is not the paper's proprietary return reproduction.")
    else:
        claims.append("Transparent reconstruction is not an exact CNE5 or optimizer reproduction.")
    if status == "not_run":
        claims.append("No performance number is reported for this blocked protocol.")
    return claims


def _write_report(output_root: Path, result: dict[str, Any], experiment_id: int) -> dict[str, str]:
    destination = output_root / result["paper_id"] / result["protocol"]
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "report.json"
    markdown_path = destination / "report.md"
    html_path = destination / "report.html"
    json_path.write_text(
        json.dumps(
            {"experiment_id": experiment_id, **result},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    markdown = _markdown(result, experiment_id)
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(
        "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Paper reproduction protocol</title>"
        "<style>body{max-width:960px;margin:2rem auto;padding:0 1rem;"
        "font-family:system-ui;line-height:1.6}code{word-break:break-all}"
        "table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:.4rem}</style>"
        f"<body><pre>{html.escape(markdown)}</pre></body></html>",
        encoding="utf-8",
    )
    if result["status"] == "not_run":
        (destination / "NOT_RUN.md").write_text(markdown, encoding="utf-8")
    return {
        "json": str(json_path),
        "markdown": str(markdown_path),
        "html": str(html_path),
    }


def _markdown(result: dict[str, Any], experiment_id: int) -> str:
    validation = result["formula_validation"]
    blockers = "\n".join(f"- {item}" for item in result["blockers"]) or "- None"
    claims = "\n".join(f"- {item}" for item in result["claims"])
    return f"""# Paper reproduction protocol report

- Experiment ID: {experiment_id}
- Paper: `{result["paper_id"]}`
- Protocol: `{result["protocol"]}`
- Status: `{result["status"]}`
- Comparability level: `{result["comparability_level"]}`
- Result hash: `{result["result_hash"]}`
- Git commit: `{result["git_commit"]}`

## Formula ledger

- Total records: {validation["total"]}
- Executable records: {validation["implemented"]}
- Manifest hash: `{validation["manifest_hash"]}`
- Synthetic smoke: {result["synthetic_smoke"]["passed"]} passed,
  {result["synthetic_smoke"]["failed"]} failed

## Blockers

{blockers}

## Permitted claims

{claims}
"""


def _registry(paper_id: str) -> FormulaRegistry:
    return load_worldquant() if paper_id == "worldquant101" else load_gtja()


def _paper_id(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "worldquant101": "worldquant101",
        "worldquant_101": "worldquant101",
        "gtja_short_cycle": "gtja_short_cycle",
        "gtja": "gtja_short_cycle",
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown paper reproduction: {value}") from exc


def _hash(value: object) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


def _git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"
