from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict
from statistics import fmean

from dyadresearch.data.models import Bar
from dyadresearch.factors.spec import FactorObservation, FactorResult, FactorSpec


class FactorEvaluator:
    def evaluate(
        self,
        spec: FactorSpec,
        bars: tuple[Bar, ...],
        *,
        data_fingerprint: str,
    ) -> FactorResult:
        grouped: dict[str, list[Bar]] = defaultdict(list)
        for bar in sorted(bars, key=lambda item: (item.symbol, item.ts)):
            grouped[bar.symbol].append(bar)
        observations: list[FactorObservation] = []
        eligible = 0
        for symbol in sorted(grouped):
            symbol_bars = grouped[symbol]
            for index in range(spec.lookback - 1, len(symbol_bars)):
                eligible += 1
                window = tuple(symbol_bars[index - spec.lookback + 1 : index + 1])
                value = spec.calculator(window)
                if value is not None and value.is_finite():
                    last = window[-1]
                    observations.append(FactorObservation(symbol, last.ts, last.trade_date, value))
        ordered = tuple(sorted(observations, key=lambda item: (item.ts, item.symbol)))
        values = [float(item.value) for item in ordered]
        summary = {
            "count": float(len(values)),
            "mean": fmean(values) if values else 0.0,
            "minimum": min(values) if values else 0.0,
            "maximum": max(values) if values else 0.0,
        }
        payload = {
            "name": spec.name,
            "version": spec.version,
            "data_fingerprint": data_fingerprint,
            "observations": [asdict(item) for item in ordered],
        }
        result_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        return FactorResult(
            name=spec.name,
            version=spec.version,
            data_fingerprint=data_fingerprint,
            result_hash=result_hash,
            observations=ordered,
            coverage_ratio=len(ordered) / eligible if eligible else 0.0,
            summary=summary,
        )
