from __future__ import annotations

import csv
import html
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dyadresearch.experiments.store import ExperimentRecord


@dataclass(frozen=True, slots=True)
class ReportArtifacts:
    html: str
    json: str
    csv: str


class ReportBuilder:
    def build(self, record: ExperimentRecord, output_root: Path) -> ReportArtifacts:
        output_root.mkdir(parents=True, exist_ok=True)
        stem = f"experiment-{record.id}-{record.result_hash[:12]}"
        json_path = output_root / f"{stem}.json"
        csv_path = output_root / f"{stem}.csv"
        html_path = output_root / f"{stem}.html"
        payload = asdict(record)
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        rows = _flatten_metrics(record.result)
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("metric", "value"))
            writer.writerows(rows)
        html_path.write_text(_html(record, rows), encoding="utf-8")
        return ReportArtifacts(str(html_path), str(json_path), str(csv_path))


def _flatten_metrics(result: dict[str, Any]) -> list[tuple[str, object]]:
    candidate = result.get("metrics", result.get("summary", {}))
    if not isinstance(candidate, dict):
        return []
    return [(str(key), candidate[key]) for key in sorted(candidate)]


def _html(record: ExperimentRecord, rows: list[tuple[str, object]]) -> str:
    table_rows = "\n".join(
        f"<tr><th>{html.escape(key)}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in rows
    )
    title = html.escape(f"DyadResearch {record.kind} #{record.id}: {record.name}")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>body{{font-family:system-ui;margin:2rem;max-width:960px}}table{{border-collapse:collapse}}
th,td{{border:1px solid #ddd;padding:.5rem;text-align:left}}code{{word-break:break-all}}</style>
</head><body><h1>{title}</h1>
<p>Created: {html.escape(record.created_at)}</p>
<p>Result hash: <code>{html.escape(record.result_hash)}</code></p>
<p>Data fingerprint: <code>{html.escape(record.data_fingerprint)}</code></p>
<h2>Metrics</h2><table>{table_rows}</table></body></html>"""
