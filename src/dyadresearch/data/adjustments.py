from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from dyadresearch.data.models import AdjustmentMode, Bar, CorporateAction

PRICE_FIELDS = ("open", "high", "low", "close", "pre_close", "settlement_price")


def adjust_bars(
    bars: tuple[Bar, ...],
    actions: tuple[CorporateAction, ...],
    *,
    mode: AdjustmentMode,
) -> tuple[Bar, ...]:
    if mode == "none" or not bars or not actions:
        return bars
    by_symbol: dict[str, list[CorporateAction]] = {}
    for action in sorted(actions, key=lambda item: item.action_date):
        by_symbol.setdefault(action.symbol, []).append(action)
    output: list[Bar] = []
    for bar in bars:
        relevant = by_symbol.get(bar.symbol, [])
        if mode in {"front", "front_ratio"}:
            relevant = [action for action in relevant if action.action_date > bar.trade_date]
        else:
            relevant = [action for action in relevant if action.action_date <= bar.trade_date]
        output.append(
            replace(
                bar,
                open=_adjust_value(bar.open, relevant, mode),
                high=_adjust_value(bar.high, relevant, mode),
                low=_adjust_value(bar.low, relevant, mode),
                close=_adjust_value(bar.close, relevant, mode),
                pre_close=_adjust_value(bar.pre_close, relevant, mode),
                settlement_price=_adjust_value(bar.settlement_price, relevant, mode),
            )
        )
    return tuple(output)


def _adjust_value(
    value: Decimal | None,
    actions: list[CorporateAction],
    mode: AdjustmentMode,
) -> Decimal | None:
    if value is None:
        return None
    adjusted = value
    if mode == "front_ratio":
        for action in actions:
            if action.dr <= 0:
                raise ValueError("corporate action dr must be positive")
            adjusted /= action.dr
        return adjusted
    if mode == "back_ratio":
        for action in actions:
            if action.dr <= 0:
                raise ValueError("corporate action dr must be positive")
            adjusted *= action.dr
        return adjusted
    if mode == "front":
        for action in actions:
            a, b = _coefficients(action)
            adjusted = a * adjusted + b
        return adjusted
    for action in reversed(actions):
        a, b = _coefficients(action)
        adjusted = (adjusted - b) / a
    return adjusted


def _coefficients(action: CorporateAction) -> tuple[Decimal, Decimal]:
    denominator = Decimal("1") + action.stock_bonus + action.stock_gift + action.allot_num
    if denominator <= 0:
        raise ValueError("corporate action share denominator must be positive")
    return (
        Decimal("1") / denominator,
        (action.allot_num * action.allot_price - action.interest) / denominator,
    )
