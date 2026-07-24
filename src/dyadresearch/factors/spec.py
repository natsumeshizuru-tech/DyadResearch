from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from dyadresearch.data.models import Bar


class FactorCalculator(Protocol):
    def __call__(self, window: tuple[Bar, ...]) -> Decimal | None: ...


@dataclass(frozen=True, slots=True)
class FactorSpec:
    name: str
    version: str
    description: str
    input_fields: tuple[str, ...]
    lookback: int
    frequency: str
    calculator: FactorCalculator
    higher_is_better: bool = True

    def __post_init__(self) -> None:
        if not self.name or not self.version:
            raise ValueError("factor name and version are required")
        if self.lookback < 1:
            raise ValueError("factor lookback must be positive")
        allowed = set(Bar.__dataclass_fields__)
        unknown = set(self.input_fields) - allowed
        if unknown:
            raise ValueError(f"unknown factor input fields: {sorted(unknown)}")


@dataclass(frozen=True, slots=True)
class FactorObservation:
    symbol: str
    ts: int
    trade_date: int
    value: Decimal


@dataclass(frozen=True, slots=True)
class FactorResult:
    name: str
    version: str
    data_fingerprint: str
    result_hash: str
    observations: tuple[FactorObservation, ...]
    coverage_ratio: float
    summary: dict[str, float]
