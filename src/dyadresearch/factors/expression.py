from __future__ import annotations

import ast
from collections.abc import Callable
from decimal import Decimal
from statistics import fmean, pstdev
from typing import Any

from dyadresearch.data.models import Bar
from dyadresearch.factors.spec import FactorCalculator, FactorSpec

ALLOWED_FUNCTIONS = {"mean", "pstdev", "returns", "sum", "min", "max", "abs"}
ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Subscript,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
)


def factor_spec_from_definition(
    *,
    name: str,
    version: int,
    description: str,
    config: dict[str, Any],
) -> FactorSpec:
    input_fields = tuple(str(item) for item in config["input_fields"])
    calculator = compile_factor_expression(str(config["expression"]), input_fields)
    return FactorSpec(
        name=name,
        version=str(version),
        description=description,
        input_fields=input_fields,
        lookback=int(config["lookback"]),
        frequency=str(config["frequency"]),
        calculator=calculator,
        higher_is_better=bool(config.get("higher_is_better", True)),
    )


def compile_factor_expression(expression: str, input_fields: tuple[str, ...]) -> FactorCalculator:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"invalid factor expression: {exc.msg}") from exc
    allowed_names = set(input_fields) | ALLOWED_FUNCTIONS
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(f"factor expression uses unsupported syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise ValueError(f"factor expression uses unknown name: {node.id}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
                raise ValueError("factor expression calls an unsupported function")
            if node.keywords:
                raise ValueError("factor expression functions do not accept keyword arguments")
    compiled = compile(tree, "<factor-expression>", "eval")

    def calculate(window: tuple[Bar, ...]) -> Decimal | None:
        values: dict[str, Any] = {
            field: tuple(getattr(bar, field) for bar in window) for field in input_fields
        }
        if any(any(item is None for item in series) for series in values.values()):
            return None
        functions: dict[str, Callable[..., Any]] = {
            "mean": _mean,
            "pstdev": _pstdev,
            "returns": _returns,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
        }
        try:
            result = eval(compiled, {"__builtins__": {}}, {**functions, **values})
        except (ArithmeticError, TypeError, ValueError, IndexError):
            return None
        if result is None:
            return None
        return result if isinstance(result, Decimal) else Decimal(str(result))

    return calculate


def _mean(values: tuple[Decimal | int, ...] | list[Decimal | int]) -> Decimal:
    return Decimal(str(fmean(float(value) for value in values)))


def _pstdev(values: tuple[Decimal | int, ...] | list[Decimal | int]) -> Decimal:
    return Decimal(str(pstdev(float(value) for value in values))) if values else Decimal("0")


def _returns(values: tuple[Decimal | int, ...] | list[Decimal | int]) -> list[Decimal]:
    converted = [Decimal(str(value)) for value in values]
    if any(value == 0 for value in converted[:-1]):
        raise ValueError("returns cannot divide by zero")
    return [converted[index] / converted[index - 1] - 1 for index in range(1, len(converted))]
