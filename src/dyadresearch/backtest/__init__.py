from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dyadresearch.backtest.engine import BacktestEngine
    from dyadresearch.backtest.policy import BacktestPolicy

__all__ = ["BacktestEngine", "BacktestPolicy", "get_policy"]


def __getattr__(name: str) -> Any:
    if name == "BacktestEngine":
        from dyadresearch.backtest.engine import BacktestEngine

        return BacktestEngine
    if name in {"BacktestPolicy", "get_policy"}:
        from dyadresearch.backtest.policy import BacktestPolicy, get_policy

        return {"BacktestPolicy": BacktestPolicy, "get_policy": get_policy}[name]
    raise AttributeError(name)
