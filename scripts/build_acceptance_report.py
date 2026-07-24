from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

EXPECTED = (
    ("worldquant101", "wq101_formula_validation"),
    ("worldquant101", "wq101_original_market"),
    ("worldquant101", "wq101_ashare_transfer"),
    ("gtja_short_cycle", "paper_strict"),
    ("gtja_short_cycle", "transparent_reconstruction"),
    ("gtja_short_cycle", "ashare_executable"),
)


def main() -> int:
    root = Path("reports/reproduction")
    protocol_root = root / "protocols"
    protocols: list[dict[str, Any]] = []
    missing: list[str] = []
    for paper_id, protocol in EXPECTED:
        path = protocol_root / paper_id / protocol / "report.json"
        if not path.is_file():
            missing.append(str(path))
            continue
        protocols.append(json.loads(path.read_text(encoding="utf-8")))
    validation_path = root / "validation.json"
    security_path = root / "security_scan.json"
    validation = _read(validation_path)
    security = _read(security_path)
    audits = {
        item["paper_id"]: item["formula_validation"]
        for item in protocols
        if item["protocol"] in {"wq101_formula_validation", "transparent_reconstruction"}
    }
    report: dict[str, Any] = {
        "schema_version": "1.0.0",
        "overall_status": "partial" if protocols and not missing else "incomplete",
        "formula_coverage": audits,
        "data_coverage": {
            "daily_bars": "2010-01-04 through 2026-07-24 in audited local data",
            "pit_financial": "2010-01-01 through 2026-07-17",
            "historical_industry": "missing; only 2026-07-17 snapshot",
            "historical_index_weights": "missing; only 2026-07-17 snapshot",
            "consensus_fields": "EPIBS/EGIB/EGIB_S unavailable",
        },
        "pit_compliance": {
            "status": "guarded_partial",
            "notes": [
                "Strict protocols reject current snapshots used as history.",
                "Day-t close signals default to t+1 execution.",
                "No full historical strategy run was performed.",
            ],
        },
        "trading_semantics": {
            "dyad_backtest_reused": True,
            "qmt_live_default": False,
            "qmt_dry_run_tested": bool(validation.get("checks", {}).get("pytest", {}).get("ok")),
        },
        "paper_comparability": {
            "worldquant_original_market": "NOT_RUN",
            "gtja_paper_strict": "NOT_RUN",
            "numeric_paper_comparison": "not performed; no fabricated values",
        },
        "out_of_sample": {
            "status": "NOT_RUN",
            "reason": (
                "full factor coverage and historical neutralization dependencies are incomplete"
            ),
        },
        "constraints_costs_turnover": {
            "optimizer": "transparent deterministic candidate with explicit violation status",
            "paper_optimizer": "not reproduced",
            "cost_sensitivity": "NOT_RUN",
            "turnover": "NOT_RUN",
        },
        "protocols": [
            {
                "experiment_id": item["experiment_id"],
                "paper_id": item["paper_id"],
                "protocol": item["protocol"],
                "status": item["status"],
                "comparability_level": item["comparability_level"],
                "result_hash": item["result_hash"],
                "blockers": item["blockers"],
            }
            for item in protocols
        ],
        "validation": validation,
        "security_scan": security,
        "missing_artifacts": missing,
        "known_limitations": [
            "WorldQuant executable coverage is not 101/101.",
            "GTJA executable coverage is not 191/191.",
            "No original-market numeric reproduction is claimed.",
            "No full A-share backtest or post-publication OOS result is claimed.",
            "Big-QMT broker-version API signatures require validation in the user's terminal.",
        ],
    }
    json_path = root / "ACCEPTANCE_REPORT.json"
    markdown_path = root / "ACCEPTANCE_REPORT.md"
    html_path = root / "ACCEPTANCE_REPORT.html"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown = _markdown(report)
    markdown_path.write_text(markdown, encoding="utf-8")
    Path("docs/reproduction/ACCEPTANCE_REPORT.md").write_text(markdown, encoding="utf-8")
    html_path.write_text(_html(report, markdown), encoding="utf-8")
    print(f"acceptance_status={report['overall_status']} protocols={len(protocols)}")
    return 0 if protocols and not missing else 1


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _markdown(report: dict[str, Any]) -> str:
    worldquant = report["formula_coverage"].get("worldquant101", {})
    gtja = report["formula_coverage"].get("gtja_short_cycle", {})
    worldquant_total = worldquant.get("total", 0)
    worldquant_implemented = worldquant.get("implemented", 0)
    worldquant_not_executable = worldquant_total - worldquant_implemented
    gtja_total = gtja.get("total", 0)
    gtja_implemented = gtja.get("implemented", 0)
    gtja_not_executable = gtja_total - gtja_implemented
    protocol_rows = "\n".join(
        f"| {item['experiment_id']} | {item['paper_id']} | {item['protocol']} | "
        f"{item['status']} | {item['comparability_level']} |"
        for item in report["protocols"]
    )
    limitations = "\n".join(f"- {item}" for item in report["known_limitations"])
    return f"""# Paper Reproduction Acceptance Report

Overall status: **{report["overall_status"].upper()}**

This is an evidence report, not a claim of completed numerical reproduction.

## Formula coverage

| Paper | Ledger | Executable and smoke-tested | Not executable |
| --- | ---: | ---: | ---: |
| WorldQuant 101 | {worldquant_total} | {worldquant_implemented} | {worldquant_not_executable} |
| GTJA short-cycle | {gtja_total} | {gtja_implemented} | {gtja_not_executable} |

## Protocols

| Experiment | Paper | Protocol | Status | Comparability |
| ---: | --- | --- | --- | --- |
{protocol_rows}

## Data and PIT

- Daily bars and PIT financial history are available locally.
- Historical industry and index-weight snapshots are not available.
- Consensus inputs EPIBS, EGIB and EGIB_S are not available.
- Strict protocols reject these gaps rather than filling them silently.

## Numerical results

- Original WorldQuant market reproduction: **NOT RUN**.
- GTJA paper-strict strategy reproduction: **NOT RUN**.
- Full A-share transfer backtest and post-2017-05 sample: **NOT RUN**.
- No paper performance values were fabricated.

## QMT and trading safety

- The existing DyadResearch backtest/broker semantics are reused.
- Big-QMT defaults to dry-run with an empty account.
- Local tests cover lot rounding, sell-first ordering, T+1 blocks, risk limits
  and deterministic user order IDs.

## Known limitations

{limitations}
"""


def _html(report: dict[str, Any], markdown: str) -> str:
    worldquant = report["formula_coverage"].get("worldquant101", {})
    gtja = report["formula_coverage"].get("gtja_short_cycle", {})

    def bar(value: int, total: int) -> str:
        width = 0 if total == 0 else round(value / total * 100, 1)
        return (
            "<div class='bar'><span style='width:"
            f"{width}%'></span></div><strong>{value}/{total}</strong>"
        )

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paper Reproduction Acceptance Report</title>
<style>
body{{margin:0;background:#07101d;color:#dbeafe;font-family:Inter,system-ui}}
main{{max-width:1050px;margin:auto;padding:48px 24px}}
.eyebrow{{color:#38bdf8;text-transform:uppercase;letter-spacing:.14em}}
h1{{font-size:42px;margin:.2em 0}} .status{{color:#fbbf24}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:28px 0}}
.card{{background:#0d1b2a;border:1px solid #21344b;border-radius:12px;padding:20px}}
.bar{{height:10px;background:#1e293b;border-radius:9px;overflow:hidden;margin:12px 0}}
.bar span{{display:block;height:100%;background:#22c55e}}
pre{{white-space:pre-wrap;background:#0b1625;border:1px solid #21344b;padding:24px;
border-radius:12px;line-height:1.55}}
@media(max-width:700px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<div class="eyebrow">DyadResearch / evidence report</div>
<h1>Paper Reproduction Acceptance</h1>
<p class="status">Overall status: {html.escape(report["overall_status"].upper())}</p>
<div class="grid">
<section class="card"><h2>WorldQuant 101</h2>
{bar(int(worldquant.get("implemented", 0)), int(worldquant.get("total", 0)))}</section>
<section class="card"><h2>GTJA 191</h2>
{bar(int(gtja.get("implemented", 0)), int(gtja.get("total", 0)))}</section>
</div>
<pre>{html.escape(markdown)}</pre>
</main></body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
