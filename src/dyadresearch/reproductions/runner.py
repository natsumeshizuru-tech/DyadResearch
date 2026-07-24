# HTML template lines intentionally remain readable as complete fragments.
# ruff: noqa: E501, RUF001

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

import yaml

from dyadresearch.config import ResearchConfig
from dyadresearch.data.periods import query_period_bars
from dyadresearch.data.query import MarketDataReader
from dyadresearch.experiments.store import ExperimentStore
from dyadresearch.factors.evaluator import FactorEvaluator
from dyadresearch.factors.examples import register_examples
from dyadresearch.factors.registry import factor_registry

CLASSIFICATIONS = {
    "EXACT_REPRODUCTION",
    "METHOD_REPRODUCTION",
    "INDEPENDENT_EXTENSION",
    "EXPLORATORY_ONLY",
}
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")


def run_reproduction(
    config: ResearchConfig, spec_path: Path, *, output_root: Path
) -> dict[str, Any]:
    spec = _load_spec(spec_path)
    dataset = _mapping(spec, "dataset")
    method = _mapping(spec, "method")
    raw_citation = _mapping(spec, "citation")
    citation = {
        "title": str(raw_citation["title"]),
        "authors": _strings(raw_citation["authors"], key="citation.authors"),
        "year": int(raw_citation["year"]),
        "identifier": str(raw_citation["identifier"]),
        "url": str(raw_citation["url"]),
    }
    identifier = str(spec["id"])
    classification = str(spec["classification"])
    symbols = _symbols(dataset.get("symbols"))
    period = str(dataset.get("period", "1d"))
    start, end = int(dataset["start"]), int(dataset["end"])
    if start > end:
        raise ValueError("reproduction dataset start must not exceed end")

    source_classification = _source_classification(config.data.root)
    expected_source = str(dataset.get("source_classification", ""))
    if expected_source and expected_source != source_classification:
        raise ValueError(f"reproduction requires {expected_source}, got {source_classification}")
    if classification == "EXACT_REPRODUCTION" and source_classification == "SYNTHETIC DATA":
        raise ValueError("synthetic data cannot support EXACT_REPRODUCTION")

    register_examples()
    factor_name = str(method["factor"])
    factor = factor_registry.get(factor_name)
    if period != factor.frequency:
        raise ValueError(f"factor {factor_name} requires period {factor.frequency}")
    query = query_period_bars(
        MarketDataReader(config.data), symbols, period=period, start=start, end=end
    )
    factor_result = FactorEvaluator().evaluate(
        factor, query.bars, data_fingerprint=query.fingerprint
    )
    direction = str(method.get("direction", "high"))
    if direction not in {"high", "low"}:
        raise ValueError("method.direction must be high or low")
    latest = _latest_ranking(factor_result.observations, direction=direction)
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "id": identifier,
        "title": str(spec["title"]),
        "classification": classification,
        "research_question": str(spec["research_question"]),
        "citation": citation,
        "method": {
            "factor": factor_name,
            "factor_version": factor.version,
            "direction": direction,
            "description": str(method["description"]),
        },
        "data": {
            "source_classification": source_classification,
            "symbols": symbols,
            "period": period,
            "start": start,
            "end": end,
            "rows": len(query.bars),
            "fingerprint": query.fingerprint,
            "artifacts": [Path(path).name for path in query.paths],
        },
        "metrics": {
            **factor_result.summary,
            "coverage_ratio": factor_result.coverage_ratio,
            "latest_cross_section_count": len(latest),
        },
        "latest_ranking": latest,
        "factor_result_hash": factor_result.result_hash,
        "limitations": _strings(spec.get("limitations"), key="limitations"),
        "reproduce": (
            f"dyadresearch reproduce run {_portable_path(spec_path)} --output reports/reproductions"
        ),
    }
    result_hash = hashlib.sha256(_canonical(payload).encode()).hexdigest()
    payload["result_hash"] = result_hash
    record = ExperimentStore(config.research.database).save(
        kind="reproduction",
        name=identifier,
        result_hash=result_hash,
        data_fingerprint=query.fingerprint,
        config={"spec": spec},
        result=payload,
    )
    artifacts = _write_artifacts(payload, output_root / identifier)
    return {
        "ok": True,
        "experiment_id": record.id,
        "classification": classification,
        "data_fingerprint": query.fingerprint,
        "result_hash": result_hash,
        "artifacts": artifacts,
    }


def _load_spec(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("reproduction spec root must be a mapping")
    for key in ("id", "title", "classification", "research_question"):
        if not isinstance(payload.get(key), str) or not str(payload[key]).strip():
            raise ValueError(f"reproduction spec requires non-empty {key}")
    if not IDENTIFIER.fullmatch(str(payload["id"])):
        raise ValueError("reproduction id must be a safe lowercase identifier")
    if payload["classification"] not in CLASSIFICATIONS:
        raise ValueError("unsupported reproduction classification")
    citation = _mapping(payload, "citation")
    for key in ("title", "authors", "year", "identifier", "url"):
        if key not in citation:
            raise ValueError(f"citation requires {key}")
    _strings(payload.get("limitations"), key="limitations")
    _mapping(payload, "method")
    _mapping(payload, "dataset")
    return payload


def _portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping")
    return value


def _strings(value: Any, *, key: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise ValueError(f"{key} must be a non-empty string list")
    return [str(item) for item in value]


def _symbols(value: Any) -> list[str]:
    symbols = sorted({item.strip().upper() for item in _strings(value, key="dataset.symbols")})
    if not symbols:
        raise ValueError("dataset.symbols must not be empty")
    return symbols


def _source_classification(data_root: Path) -> str:
    marker = data_root / "SYNTHETIC_DATA.json"
    if not marker.is_file():
        return "LICENSED LOCAL DATA"
    payload = json.loads(marker.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and payload.get("classification") == "SYNTHETIC DATA":
        return "SYNTHETIC DATA"
    raise ValueError(f"invalid synthetic-data marker: {marker}")


def _latest_ranking(observations: tuple[Any, ...], *, direction: str) -> list[dict[str, Any]]:
    latest: dict[str, Any] = {}
    for observation in observations:
        previous = latest.get(observation.symbol)
        if previous is None or observation.ts > previous.ts:
            latest[observation.symbol] = observation
    ordered = sorted(
        latest.values(),
        key=lambda item: (item.value, item.symbol),
        reverse=direction == "high",
    )
    return [
        {
            "rank": rank,
            "symbol": item.symbol,
            "trade_date": item.trade_date,
            "value": str(item.value),
        }
        for rank, item in enumerate(ordered, start=1)
    ]


def _write_artifacts(payload: dict[str, Any], output: Path) -> dict[str, str]:
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "report.json"
    csv_path = output / "metrics.csv"
    html_path = output / "report.html"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("metric", "value"))
        writer.writerows(sorted(payload["metrics"].items()))
    html_path.write_text(_html(payload), encoding="utf-8")
    return {"html": str(html_path), "json": str(json_path), "csv": str(csv_path)}


def _html(payload: dict[str, Any]) -> str:
    def esc(value: object) -> str:
        return html.escape(str(value))

    citation = payload["citation"]
    metrics = "".join(
        f"<tr><th>{esc(key)}</th><td>{esc(value)}</td></tr>"
        for key, value in sorted(payload["metrics"].items())
    )
    limitations = "".join(f"<li>{esc(item)}</li>" for item in payload["limitations"])
    ranking = "".join(
        f"<tr><td>{item['rank']}</td><td>{esc(item['symbol'])}</td>"
        f"<td>{esc(item['trade_date'])}</td><td>{esc(item['value'])}</td></tr>"
        for item in payload["latest_ranking"]
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(payload["title"])}</title>
<style>body{{font-family:system-ui;margin:2rem auto;max-width:960px;padding:0 1rem}}
.badge{{display:inline-block;padding:.3rem .6rem;background:#ffe8a3;color:#4b3900;font-weight:700}}
table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid #ddd;padding:.5rem;text-align:left}}
code{{word-break:break-all}}</style></head><body>
<p class="badge">{esc(payload["classification"])}</p><h1>{esc(payload["title"])}</h1>
<p><strong>Research question:</strong> {esc(payload["research_question"])}</p>
<h2>Citation</h2><p>{esc(", ".join(citation["authors"]))} ({esc(citation["year"])}).
{esc(citation["title"])}. <a href="{esc(citation["url"])}">{esc(citation["identifier"])}</a>.</p>
<h2>Method and data</h2><p>{esc(payload["method"]["description"])}</p>
<p>Data classification: <strong>{esc(payload["data"]["source_classification"])}</strong>;
range {esc(payload["data"]["start"])}–{esc(payload["data"]["end"])}; rows {esc(payload["data"]["rows"])}.</p>
<p>Data fingerprint: <code>{esc(payload["data"]["fingerprint"])}</code><br>
Result hash: <code>{esc(payload["result_hash"])}</code></p>
<h2>Metrics</h2><table>{metrics}</table>
<h2>Latest synthetic cross-section</h2><table><tr><th>Rank</th><th>Symbol</th>
<th>Date</th><th>Value</th></tr>{ranking}</table>
<h2>Limitations</h2><ul>{limitations}</ul>
<h2>Reproduce</h2><pre><code>{esc(payload["reproduce"])}</code></pre>
</body></html>"""


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
