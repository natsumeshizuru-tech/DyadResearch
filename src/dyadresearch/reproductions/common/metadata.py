from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class FormulaStatus(StrEnum):
    EXACT = "exact"
    NORMALIZED = "normalized"
    CORRECTED_TYPO = "corrected_typo"
    ASSUMPTION = "assumption"
    UNAVAILABLE_DEPENDENCY = "unavailable_dependency"
    NOT_IMPLEMENTED = "not_implemented"


@dataclass(frozen=True, slots=True)
class FormulaRecord:
    paper_id: str
    factor_id: str
    title: str
    source_expression: str
    normalized_expression: str
    implementation: str
    required_fields: tuple[str, ...]
    required_history: int
    cross_sectional_or_time_series: str
    delay: int
    execution_timing: str
    industry_neutralization: str
    formula_status: FormulaStatus
    ambiguity_notes: tuple[str, ...]
    source_page: int
    tests: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> FormulaRecord:
        return cls(
            paper_id=_required_text(value, "paper_id"),
            factor_id=_required_text(value, "factor_id"),
            title=_required_text(value, "title"),
            source_expression=_required_text(value, "source_expression"),
            normalized_expression=str(value.get("normalized_expression", "")),
            implementation=str(value.get("implementation", "")),
            required_fields=_text_tuple(value.get("required_fields", []), "required_fields"),
            required_history=int(value.get("required_history", 1)),
            cross_sectional_or_time_series=_required_text(value, "cross_sectional_or_time_series"),
            delay=int(value.get("delay", 1)),
            execution_timing=_required_text(value, "execution_timing"),
            industry_neutralization=_required_text(value, "industry_neutralization"),
            formula_status=FormulaStatus(_required_text(value, "formula_status")),
            ambiguity_notes=_text_tuple(value.get("ambiguity_notes", []), "ambiguity_notes"),
            source_page=int(value["source_page"]),
            tests=_text_tuple(value.get("tests", []), "tests"),
        )

    def __post_init__(self) -> None:
        if self.required_history < 1:
            raise ValueError(f"{self.factor_id}: required_history must be positive")
        if self.delay < 0:
            raise ValueError(f"{self.factor_id}: delay cannot be negative")
        if self.source_page < 1:
            raise ValueError(f"{self.factor_id}: source_page must be positive")
        if self.formula_status not in {
            FormulaStatus.UNAVAILABLE_DEPENDENCY,
            FormulaStatus.NOT_IMPLEMENTED,
        } and (not self.normalized_expression or not self.implementation or not self.tests):
            raise ValueError(
                f"{self.factor_id}: implemented formulas require expression, "
                "implementation and tests"
            )


def _required_text(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise ValueError(f"formula record requires non-empty {key}")
    return item.strip()


def _text_tuple(value: Any, key: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a string list")
    return tuple(item.strip() for item in value if item.strip())
