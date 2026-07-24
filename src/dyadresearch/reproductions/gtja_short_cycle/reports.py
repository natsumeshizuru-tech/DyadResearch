from __future__ import annotations

from typing import Any


def disclosure(result: dict[str, Any]) -> str:
    if result["protocol"] == "paper_strict":
        return (
            "NOT RUN as a numerical strategy reproduction: historical industry/"
            "benchmark snapshots and consensus fields are unavailable."
        )
    return (
        "Transparent reconstruction uses explicitly reduced dependencies and "
        "must not be compared directly with the paper's absolute returns."
    )
