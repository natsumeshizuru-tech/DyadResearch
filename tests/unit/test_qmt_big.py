from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def _load(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    root = project_root / "qmt_big"
    monkeypatch.syspath_prepend(str(root))
    spec = importlib.util.spec_from_file_location(
        "qmt_target_executor", root / "target_weight_executor.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_qmt_default_is_dry_run(project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    executor = _load(project_root, monkeypatch)
    assert executor.CONFIG.ENABLE_LIVE_TRADING is False
    assert executor.CONFIG.ACCOUNT_ID == ""
    assert executor.CONFIG.QUICK_TRADE in (0, 1)


def test_qmt_plan_rounds_lots_sells_first_and_reports_t1(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executor = _load(project_root, monkeypatch)
    config = SimpleNamespace(
        LOT_SIZE=100,
        MIN_ORDER_NOTIONAL=100.0,
        MAX_ORDER_NOTIONAL=1_000_000.0,
        MAX_DAILY_TURNOVER=2.0,
    )
    signal_hash = "a" * 64
    targets = [
        {
            "stock_code": "000001.SZ",
            "target_weight": 0.7,
            "reference_price": 10.0,
            "experiment_id": "exp-1",
            "signal_hash": signal_hash,
        },
        {
            "stock_code": "600000.SH",
            "target_weight": 0.3,
            "reference_price": 10.0,
            "experiment_id": "exp-1",
            "signal_hash": signal_hash,
        },
    ]
    plan = executor.build_order_plan(
        targets,
        100_000.0,
        10_000.0,
        {"000001.SZ": 9_000},
        {"000001.SZ": 1_000},
        {"000001.SZ": 10.0, "600000.SH": 10.0},
        config,
    )
    assert plan[0]["side"] == "SELL"
    assert plan[1]["side"] == "BUY"
    assert any(item["side"] == "BLOCKED_T1" for item in plan)
    assert all(item["quantity"] % 100 == 0 for item in plan if item["side"] == "BUY")
    again = executor.build_order_plan(
        targets,
        100_000.0,
        10_000.0,
        {"000001.SZ": 9_000},
        {"000001.SZ": 1_000},
        {"000001.SZ": 10.0, "600000.SH": 10.0},
        config,
    )
    assert [item["user_order_id"] for item in plan] == [item["user_order_id"] for item in again]
