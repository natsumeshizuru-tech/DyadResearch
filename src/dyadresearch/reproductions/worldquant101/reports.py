from __future__ import annotations

from typing import Any


def disclosure(result: dict[str, Any]) -> str:
    if result["protocol"] == "wq101_original_market":
        return (
            "NOT RUN: equivalent proprietary WorldQuant US data, universe, "
            "industry history and realized alpha returns are not available."
        )
    return (
        "Formula engineering and A-share transfer evidence are not a numerical "
        "reproduction of the paper's proprietary realized returns."
    )
