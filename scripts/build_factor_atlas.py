from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from dyadresearch.reproductions.common.registry import FormulaRegistry


def main() -> int:
    source = Path("src/dyadresearch/reproductions")
    registries = {
        "worldquant101": FormulaRegistry.load(source / "worldquant101/manifest.yaml"),
        "gtja_short_cycle": FormulaRegistry.load(source / "gtja_short_cycle/manifest.yaml"),
    }
    rows: list[dict[str, Any]] = []
    expressions: dict[str, list[str]] = defaultdict(list)
    for paper_id, registry in registries.items():
        for record in registry.records:
            expression = record.normalized_expression or record.source_expression
            fingerprint = hashlib.sha256(_canonical(expression).encode()).hexdigest()[:16]
            key = f"{paper_id}:{record.factor_id}"
            expressions[fingerprint].append(key)
            rows.append(
                {
                    "paper_id": paper_id,
                    "factor_id": record.factor_id,
                    "formula_status": record.formula_status.value,
                    "family": _family(expression),
                    "required_fields": list(record.required_fields),
                    "required_history": record.required_history,
                    "delay": record.delay,
                    "source_page": record.source_page,
                    "fingerprint": fingerprint,
                }
            )
    for row in rows:
        key = f"{row['paper_id']}:{row['factor_id']}"
        row["exact_fingerprint_matches"] = [
            value for value in expressions[row["fingerprint"]] if value != key
        ]
    output = {
        "schema_version": "1.0.0",
        "records": rows,
        "summary": {
            paper_id: {
                "total": len(registry.records),
                "status_counts": registry.status_counts(),
            }
            for paper_id, registry in registries.items()
        },
    }
    report_root = Path("reports/reproduction")
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / "factor_atlas.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path("docs/reproduction/FACTOR_ATLAS.md").write_text(
        _markdown(rows, output["summary"]), encoding="utf-8"
    )
    print(f"factor_atlas_records={len(rows)}")
    return 0


def _canonical(expression: str) -> str:
    return re.sub(r"\s+", "", expression).lower()


def _family(expression: str) -> str:
    value = expression.lower()
    if "correlation" in value or "corr(" in value or "covariance" in value:
        return "correlation"
    if "std" in value or "high - low" in value or "high-low" in value:
        return "volatility"
    if "volume" in value or "amount" in value or "adv" in value:
        return "liquidity_or_volume"
    if "open" in value and ("delay(close" in value or "close" in value):
        return "open_gap_or_intraday"
    if "delta" in value or "delay" in value or "returns" in value or "ret" in value:
        return "momentum_or_reversal"
    if "ts_min" in value or "ts_max" in value or "rank" in value:
        return "position"
    return "other"


def _markdown(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# Factor Atlas",
        "",
        "The atlas compares normalized structural fingerprints, input dependencies,",
        "lookback, delay and implementation status. It does not publish backtest",
        "performance for protocols that did not run.",
        "",
        "## Summary",
        "",
        "| Paper | Records | Status counts |",
        "| --- | ---: | --- |",
    ]
    for paper_id, values in summary.items():
        counts = ", ".join(
            f"{key}={value}" for key, value in values["status_counts"].items() if value
        )
        lines.append(f"| {paper_id} | {values['total']} | {counts} |")
    lines.extend(
        [
            "",
            "## Formula records",
            "",
            "| Paper | Factor | Status | Family | Fields | History | Delay | Page | Fingerprint |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        fields = ", ".join(row["required_fields"]) or "-"
        lines.append(
            f"| {row['paper_id']} | {row['factor_id']} | {row['formula_status']} "
            f"| {row['family']} | {fields} | {row['required_history']} | {row['delay']} "
            f"| {row['source_page']} | `{row['fingerprint']}` |"
        )
    lines.extend(
        [
            "",
            "Machine-readable records and exact-fingerprint links are in",
            "`reports/reproduction/factor_atlas.json`.",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
