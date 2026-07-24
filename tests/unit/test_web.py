from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from dyadresearch.data.models import Bar, CorporateAction
from dyadresearch.errors import DataCapabilityError
from dyadresearch.web import (
    BacktestRunRequest,
    _benchmark_curve,
    _corporate_action_fingerprint,
    _decode_json,
    _experiment_metrics,
    _extended_metrics,
    _safe,
    _total_return_benchmark_bars,
    _workflow_metrics,
)


def test_extended_metrics_adds_research_summary_fields() -> None:
    result = {
        "metrics": {"total_return": 0.21, "max_drawdown": -0.08},
        "equity": [
            {"net_value": 1.0},
            {"net_value": 1.1},
            {"net_value": 1.21},
        ],
    }

    metrics = _extended_metrics(result)

    assert metrics["total_return"] == pytest.approx(0.21)
    assert metrics["max_drawdown"] == pytest.approx(-0.08)
    assert metrics["ending_net_value"] == pytest.approx(1.21)
    assert metrics["annualized_return"] > 0
    assert metrics["sharpe"] >= 0


def test_safe_converts_local_data_errors_to_http_400() -> None:
    def fail() -> None:
        raise ValueError("invalid local research request")

    with pytest.raises(HTTPException) as error:
        _safe(fail)

    assert error.value.status_code == 400
    assert error.value.detail == "invalid local research request"

    def fail_capability() -> None:
        raise DataCapabilityError("outside coverage")

    with pytest.raises(HTTPException) as capability_error:
        _safe(fail_capability)
    assert capability_error.value.status_code == 400
    assert capability_error.value.detail == "outside coverage"


def test_backtest_request_keeps_research_safety_defaults() -> None:
    request = BacktestRunRequest()

    assert request.policy == "strict_research"
    assert request.initial_cash == Decimal("1000000")
    assert request.start == 20240102
    assert request.end == 20260717
    assert request.benchmark_symbol == "510300.SH"
    assert request.commission_rate == Decimal("0.0001")
    assert request.minimum_commission == Decimal("5")
    assert request.stamp_duty_rate == Decimal("0.0005")

    with pytest.raises(ValidationError):
        BacktestRunRequest(quantity=1)


def test_real_benchmark_curve_aligns_etf_closes_to_equity_timeline() -> None:
    bars = tuple(
        Bar(
            symbol="510300.SH",
            ts=ts,
            trade_date=20240100 + index,
            open=Decimal(close),
            high=Decimal(close),
            low=Decimal(close),
            close=Decimal(close),
            volume=1,
            amount=Decimal(close),
        )
        for index, (ts, close) in enumerate(((1, "4"), (3, "5")), start=1)
    )

    curve = _benchmark_curve([{"ts": 1}, {"ts": 2}, {"ts": 3}], bars)

    assert [point["net_value"] for point in curve] == [1.0, 1.0, 1.25]

    with pytest.raises(ValueError, match="starts before"):
        _benchmark_curve([{"ts": 0}], bars)


def test_etf_benchmark_uses_total_return_adjustment() -> None:
    bars = tuple(
        Bar(
            symbol="510300.SH",
            ts=ts,
            trade_date=trade_date,
            open=Decimal(close),
            high=Decimal(close),
            low=Decimal(close),
            close=Decimal(close),
            volume=1,
            amount=Decimal(close),
        )
        for ts, trade_date, close in (
            (1, 20240101, "10"),
            (2, 20240102, "9"),
        )
    )
    action = CorporateAction(
        symbol="510300.SH",
        action_date=20240102,
        interest=Decimal("1"),
        stock_bonus=Decimal("0"),
        stock_gift=Decimal("0"),
        allot_num=Decimal("0"),
        allot_price=Decimal("0"),
        dr=Decimal("10") / Decimal("9"),
    )

    adjusted = _total_return_benchmark_bars(bars, (action,))
    curve = _benchmark_curve([{"ts": 1}, {"ts": 2}], adjusted)

    assert [point["net_value"] for point in curve] == pytest.approx([1.0, 1.0])
    assert _benchmark_curve([{"ts": 1}, {"ts": 2}], bars)[-1]["net_value"] == 0.9


def test_corporate_actions_are_part_of_data_fingerprint() -> None:
    base = CorporateAction(
        symbol="510300.SH",
        action_date=20240102,
        interest=Decimal("0.1"),
        stock_bonus=Decimal("0"),
        stock_gift=Decimal("0"),
        allot_num=Decimal("0"),
        allot_price=Decimal("0"),
        dr=Decimal("1.01"),
    )
    changed = CorporateAction(
        symbol=base.symbol,
        action_date=base.action_date,
        interest=Decimal("0.2"),
        stock_bonus=base.stock_bonus,
        stock_gift=base.stock_gift,
        allot_num=base.allot_num,
        allot_price=base.allot_price,
        dr=Decimal("1.02"),
    )

    assert _corporate_action_fingerprint((base,)) != _corporate_action_fingerprint((changed,))


def test_factor_experiment_metrics_expose_summary_and_coverage() -> None:
    metrics = _experiment_metrics(
        "factor",
        {
            "coverage_ratio": 0.75,
            "summary": {"count": 3.0, "mean": 0.1, "minimum": -0.2, "maximum": 0.4},
        },
    )

    assert metrics["coverage_ratio"] == pytest.approx(0.75)
    assert metrics["count"] == pytest.approx(3)
    assert metrics["maximum"] == pytest.approx(0.4)


def test_workflow_metrics_flattens_numeric_result_sections() -> None:
    metrics = _workflow_metrics(
        {
            "coverage_ratio": 0.8,
            "ok": True,
            "summary": {"count": 12, "label": "ignored"},
            "metrics": {"sharpe": Decimal("1.25")},
        }
    )

    assert metrics == {
        "coverage_ratio": 0.8,
        "summary.count": 12,
        "metrics.sharpe": 1.25,
    }


def test_financial_raw_json_decoder_preserves_invalid_source_text() -> None:
    assert _decode_json('{"revenue": 1}') == {"revenue": 1}
    assert _decode_json("not-json") == {"raw": "not-json"}
