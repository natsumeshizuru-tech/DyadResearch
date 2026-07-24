"""Extract formula ledgers from the two user-provided source PDFs.

This provenance tool is intentionally not run in CI and never copies a PDF
into the repository. It requires pypdf in the invoking environment.
"""
# ruff: noqa: RUF001

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml
from pypdf import PdfReader

FIELDS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "vwap",
    "returns",
    "cap",
    "mkt",
    "smb",
    "hml",
)

WQ_NORMALIZED = {
    2: "-1 * correlation(rank(delta(log(volume), 2)), rank((close - open) / open), 6)",
    3: "-1 * correlation(rank(open), rank(volume), 10)",
    4: "-1 * ts_rank(rank(low), 9)",
    5: "rank(open - mean(vwap, 10)) * -1 * abs(rank(close - vwap))",
    6: "-1 * correlation(open, volume, 10)",
    12: "sign(delta(volume, 1)) * -1 * delta(close, 1)",
    13: "-1 * rank(covariance(rank(close), rank(volume), 5))",
    15: "-1 * sum(rank(correlation(rank(high), rank(volume), 3)), 3)",
    18: "-1 * rank(stddev(abs(close - open), 5) + (close - open) + correlation(close, open, 10))",
    20: (
        "-1 * rank(open - delay(high, 1)) * rank(open - delay(close, 1)) "
        "* rank(open - delay(low, 1))"
    ),
    37: "rank(correlation(delay(open - close, 1), close, 200)) + rank(open - close)",
    42: "rank(vwap - close) / rank(vwap + close)",
    54: "-1 * ((low - close) * (open ** 5)) / ((low - high) * (close ** 5))",
    65: "-1 * rank(correlation(open, mean(volume, 60), 6)) * rank(open - ts_min(open, 14))",
    101: "(close - open) / (high - low + 0.001)",
}

GTJA_NORMALIZED = {
    1: "-1 * correlation(rank(delta(log(volume), 1)), rank((close - open) / open), 6)",
    2: "-1 * delta(((close - low) - (high - close)) / (high - low), 1)",
    6: "-1 * rank(sign(delta(open * 0.85 + high * 0.15, 4)))",
    8: "-1 * rank(delta(((high + low) / 2) * 0.2 + vwap * 0.8, 4))",
    9: (
        "sma((((high + low) / 2) - ((delay(high, 1) + delay(low, 1)) / 2)) "
        "* (high - low) / volume, 7, 2)"
    ),
    13: "signed_power(high * low, 0.5) - vwap",
    14: "close - delay(close, 5)",
    15: "open / delay(close, 1) - 1",
    18: "close / delay(close, 5)",
    20: "(close - delay(close, 6)) / delay(close, 6) * 100",
    31: "(close - mean(close, 12)) / mean(close, 12) * 100",
    34: "mean(close, 12) / close",
    53: "count(close > delay(close, 1), 12) / 12 * 100",
    58: "count(close > delay(close, 1), 20) / 20 * 100",
    65: "mean(close, 6) / close",
    66: "(close - mean(close, 6)) / mean(close, 6) * 100",
    70: "stddev(amount, 6)",
    71: "(close - mean(close, 24)) / mean(close, 24) * 100",
    80: "(volume - delay(volume, 5)) / delay(volume, 5) * 100",
    81: "sma(volume, 21, 2)",
    88: "(close - delay(close, 20)) / delay(close, 20) * 100",
    95: "stddev(amount, 20)",
    97: "stddev(volume, 10)",
    100: "stddev(volume, 20)",
    102: (
        "sma(max(volume - delay(volume, 1), 0), 6, 1) "
        "/ sma(abs(volume - delay(volume, 1)), 6, 1) * 100"
    ),
    106: "close - delay(close, 20)",
    143: (
        "self_previous * where(close > delay(close, 1), "
        "(close - delay(close, 1)) / delay(close, 1), 1)"
    ),
    191: "correlation(mean(volume, 20), low, 5) + ((high + low) / 2) - close",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worldquant", required=True, type=Path)
    parser.add_argument("--gtja", required=True, type=Path)
    parser.add_argument("--output-root", type=Path, default=Path("src/dyadresearch/reproductions"))
    args = parser.parse_args()

    worldquant = _extract(
        args.worldquant,
        paper_id="worldquant101",
        marker=re.compile(r"(?m)^Alpha#(\d+)\s*:?\s*"),
        first_page=8,
        last_page=15,
        normalized=WQ_NORMALIZED,
        delay_zero={42, 48, 53, 54},
    )
    gtja = _extract(
        args.gtja,
        paper_id="gtja_short_cycle",
        marker=re.compile(r"(?m)^Alpha(\d+)\s+"),
        first_page=11,
        last_page=17,
        normalized=GTJA_NORMALIZED,
        delay_zero=set(),
    )
    _write(args.output_root / "worldquant101" / "manifest.yaml", "worldquant101", worldquant)
    _write(args.output_root / "gtja_short_cycle" / "manifest.yaml", "gtja_short_cycle", gtja)
    print(f"worldquant101={len(worldquant)} gtja_short_cycle={len(gtja)}")
    return 0


def _extract(
    path: Path,
    *,
    paper_id: str,
    marker: re.Pattern[str],
    first_page: int,
    last_page: int,
    normalized: dict[int, str],
    delay_zero: set[int],
) -> list[dict[str, Any]]:
    pages = PdfReader(path).pages
    selected = [
        (number, pages[number - 1].extract_text() or "")
        for number in range(first_page, last_page + 1)
    ]
    joined = "\n".join(f"\n@@PAGE={number}@@\n{text}" for number, text in selected)
    matches = list(marker.finditer(joined))
    factors: dict[int, dict[str, Any]] = {}
    for index, match in enumerate(matches):
        number = int(match.group(1))
        if not 1 <= number <= (101 if paper_id == "worldquant101" else 191):
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(joined)
        block = joined[match.end() : end]
        block = block.split("@@PAGE=", 1)[0]
        block = block.split("A.1. Functions and Operators", 1)[0]
        block = block.split("数据来源：", 1)[0]
        page_match = list(re.finditer(r"@@PAGE=(\d+)@@", joined[: match.start()]))
        page = int(page_match[-1].group(1)) if page_match else first_page
        expression = re.sub(r"@@PAGE=\d+@@", " ", block)
        expression = re.sub(r"\s+", " ", expression).strip()
        normalized_expression = normalized.get(number, "")
        required_fields = [
            field for field in FIELDS if re.search(rf"\b{field}\b", expression, re.IGNORECASE)
        ]
        history_numbers = [
            int(float(item))
            for item in re.findall(r"(?<![A-Za-z])(\d+(?:\.\d+)?)", expression)
            if float(item) >= 1
        ]
        ambiguity: list[str] = []
        unavailable = any(
            re.search(rf"\b{dependency}\b", expression, re.IGNORECASE)
            for dependency in ("MKT", "SMB", "HML", "BANCHMARK", "INDCLASS")
        )
        if paper_id == "gtja_short_cycle" and re.search(
            r"[？：，]|COVIANCE|BANCHMARK|CL OSE|STD\([^,]+:|SMEAN", expression
        ):
            ambiguity.append("Source contains typography, spelling or delimiter ambiguity.")
        status = "normalized" if normalized_expression else "not_implemented"
        if unavailable and not normalized_expression:
            status = "unavailable_dependency"
        factors[number] = {
            "paper_id": paper_id,
            "factor_id": f"alpha{number:03d}",
            "title": f"Alpha {number}",
            "source_expression": expression,
            "normalized_expression": normalized_expression,
            "implementation": ("restricted_expression_ast" if normalized_expression else ""),
            "required_fields": required_fields,
            "required_history": max(history_numbers, default=1),
            "cross_sectional_or_time_series": (
                "mixed"
                if re.search(r"\bRANK\b|IndNeutralize", expression, re.IGNORECASE)
                else "time_series"
            ),
            "delay": 0 if number in delay_zero else 1,
            "execution_timing": (
                "same_day_close_approximation" if number in delay_zero else "next_session_open"
            ),
            "industry_neutralization": (
                "formula_required"
                if re.search(r"IndNeutralize", expression, re.IGNORECASE)
                else "none"
            ),
            "formula_status": status,
            "ambiguity_notes": ambiguity,
            "source_page": page,
            "tests": (
                [
                    "tests/unit/test_paper_formulas.py::"
                    "test_executable_manifest_formulas_on_synthetic_panel"
                ]
                if normalized_expression
                else []
            ),
        }
    expected = 101 if paper_id == "worldquant101" else 191
    missing = sorted(set(range(1, expected + 1)) - set(factors))
    if missing:
        raise ValueError(f"{paper_id}: failed to extract formula IDs {missing}")
    return [factors[number] for number in range(1, expected + 1)]


def _write(path: Path, paper_id: str, factors: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "paper_id": paper_id,
        "version": "2026-07-25",
        "factors": factors,
    }
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
