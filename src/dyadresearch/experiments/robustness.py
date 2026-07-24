from __future__ import annotations

import itertools
import random
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from statistics import fmean
from typing import Any


@dataclass(frozen=True, slots=True)
class WalkForwardSplit:
    train_start: int
    train_end: int
    test_start: int
    test_end: int


def walk_forward_splits(
    observations: int, *, train_size: int, test_size: int, step: int | None = None
) -> tuple[WalkForwardSplit, ...]:
    if min(observations, train_size, test_size) <= 0:
        raise ValueError("walk-forward sizes must be positive")
    stride = test_size if step is None else step
    if stride <= 0:
        raise ValueError("walk-forward step must be positive")
    result: list[WalkForwardSplit] = []
    train_start = 0
    while train_start + train_size + test_size <= observations:
        train_end = train_start + train_size
        result.append(WalkForwardSplit(train_start, train_end, train_end, train_end + test_size))
        train_start += stride
    return tuple(result)


def monte_carlo_compounded_returns(
    returns: Sequence[float], *, simulations: int = 1000, seed: int = 0
) -> dict[str, float]:
    if not returns or simulations <= 0:
        raise ValueError("Monte Carlo requires returns and positive simulations")
    generator = random.Random(seed)
    outcomes: list[float] = []
    for _ in range(simulations):
        value = 1.0
        for _ in returns:
            value *= 1.0 + generator.choice(returns)
        outcomes.append(value - 1.0)
    ordered = sorted(outcomes)
    return {
        "simulations": float(simulations),
        "mean": fmean(outcomes),
        "p05": ordered[int((simulations - 1) * 0.05)],
        "p50": ordered[int((simulations - 1) * 0.50)],
        "p95": ordered[int((simulations - 1) * 0.95)],
    }


def grid_search(
    space: Mapping[str, Iterable[Any]],
    objective: Callable[[dict[str, Any]], float],
    *,
    maximize: bool = True,
) -> tuple[tuple[dict[str, Any], float], ...]:
    names = sorted(space)
    values = [tuple(space[name]) for name in names]
    if not names or any(not value for value in values):
        raise ValueError("grid search space cannot be empty")
    results = []
    for combination in itertools.product(*values):
        parameters = dict(zip(names, combination, strict=True))
        results.append((parameters, float(objective(parameters))))
    return tuple(sorted(results, key=lambda item: item[1], reverse=maximize))
