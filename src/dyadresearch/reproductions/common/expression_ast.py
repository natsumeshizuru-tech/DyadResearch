from __future__ import annotations

import ast
import operator
import re
from collections.abc import Callable
from typing import Any

import numpy as np

from dyadresearch.reproductions.common.operators import OPERATOR_REGISTRY

_ALIASES = {
    "corr": "correlation",
    "coviance": "covariance",
    "covariance": "covariance",
    "decaylinear": "decay_linear",
    "signedpower": "signed_power",
    "std": "stddev",
    "tsargmax": "ts_argmax",
    "tsargmin": "ts_argmin",
    "tsmax": "ts_max",
    "tsmin": "ts_min",
    "tsrank": "ts_rank",
}
_BINARY: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: np.logical_not,
}
_COMPARE: dict[type[ast.cmpop], Callable[[Any, Any], Any]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def normalize_expression(source: str) -> str:
    value = source.strip().replace("^", "**").replace("\uff0c", ",")
    value = re.sub(r"\bAND\b|&&", " and ", value, flags=re.IGNORECASE)
    value = re.sub(r"\bOR\b|\|\|", " or ", value, flags=re.IGNORECASE)
    tokens = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", value))
    for token in sorted(tokens, key=len, reverse=True):
        lowered = token.lower()
        replacement = _ALIASES.get(lowered, lowered)
        value = re.sub(rf"\b{re.escape(token)}\b", replacement, value)
    return value


class RestrictedExpression:
    def __init__(self, expression: str) -> None:
        self.expression = normalize_expression(expression)
        try:
            self.tree = ast.parse(self.expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"paper expression is not normalized: {exc.msg}") from exc
        self._validate(self.tree)

    def evaluate(self, inputs: dict[str, Any]) -> Any:
        return _evaluate(self.tree.body, {**OPERATOR_REGISTRY, **inputs})

    @staticmethod
    def _validate(tree: ast.AST) -> None:
        allowed = (
            ast.Expression,
            ast.BinOp,
            ast.UnaryOp,
            ast.BoolOp,
            ast.Compare,
            ast.Call,
            ast.Name,
            ast.Load,
            ast.Constant,
            ast.IfExp,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.Pow,
            ast.Mod,
            ast.UAdd,
            ast.USub,
            ast.Not,
            ast.And,
            ast.Or,
            ast.Eq,
            ast.NotEq,
            ast.Lt,
            ast.LtE,
            ast.Gt,
            ast.GtE,
        )
        for node in ast.walk(tree):
            if not isinstance(node, allowed):
                raise ValueError(f"unsupported paper-expression syntax: {type(node).__name__}")
            if isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id not in OPERATOR_REGISTRY:
                    raise ValueError("paper expression calls an unregistered operator")
                if node.keywords:
                    raise ValueError("paper-expression operators do not accept keyword arguments")


def _evaluate(node: ast.AST, context: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in context:
            raise ValueError(f"paper expression requires unknown input: {node.id}")
        return context[node.id]
    if isinstance(node, ast.BinOp):
        return _BINARY[type(node.op)](_evaluate(node.left, context), _evaluate(node.right, context))
    if isinstance(node, ast.UnaryOp):
        return _UNARY[type(node.op)](_evaluate(node.operand, context))
    if isinstance(node, ast.Compare):
        left = _evaluate(node.left, context)
        result: Any = True
        for operation, comparator in zip(node.ops, node.comparators, strict=True):
            right = _evaluate(comparator, context)
            result = np.logical_and(result, _COMPARE[type(operation)](left, right))
            left = right
        return result
    if isinstance(node, ast.BoolOp):
        values = [_evaluate(value, context) for value in node.values]
        function = np.logical_and if isinstance(node.op, ast.And) else np.logical_or
        result = values[0]
        for value in values[1:]:
            result = function(result, value)
        return result
    if isinstance(node, ast.IfExp):
        return OPERATOR_REGISTRY["where"](
            _evaluate(node.test, context),
            _evaluate(node.body, context),
            _evaluate(node.orelse, context),
        )
    if isinstance(node, ast.Call):
        assert isinstance(node.func, ast.Name)
        function = context[node.func.id]
        return function(*(_evaluate(argument, context) for argument in node.args))
    raise ValueError(f"unsupported expression node: {type(node).__name__}")
