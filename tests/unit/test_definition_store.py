import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from dyadresearch.data.models import Bar
from dyadresearch.experiments.definitions import (
    LEGACY_BUY_AND_HOLD_CODE,
    LOW_VOLUME_RATIO_CODE,
    DefinitionStore,
)
from dyadresearch.factors.expression import factor_spec_from_definition


def test_definition_store_crud_and_builtin_protection(tmp_path: Path) -> None:
    store = DefinitionStore(tmp_path / "research.db")

    assert {item.name for item in store.list("strategy")} == {
        "buy_and_hold",
        "moving_average_cross",
    }
    created = store.create("strategy", "low_volume_ratio_momentum", LOW_VOLUME_RATIO_CODE)
    assert created.implementation == "low_volume_ratio_momentum"
    assert created.config["parameters"]["volume_ratio_max"] == pytest.approx(0.6)

    changed_code = LOW_VOLUME_RATIO_CODE.replace(
        '"volume_ratio_max": 0.60', '"volume_ratio_max": 0.55'
    )
    updated = store.update("strategy", created.name, changed_code)
    assert updated.version == 2
    assert updated.config["parameters"]["volume_ratio_max"] == pytest.approx(0.55)

    store.delete("strategy", created.name)
    with pytest.raises(KeyError, match="unknown strategy"):
        store.get("strategy", created.name)
    with pytest.raises(ValueError, match="built-in"):
        store.delete("strategy", "buy_and_hold")


def test_persisted_factor_expression_is_executable(tmp_path: Path) -> None:
    definition = DefinitionStore(tmp_path / "research.db").get("factor", "momentum_20")
    spec = factor_spec_from_definition(
        name=definition.name,
        version=definition.version,
        description=definition.description,
        config=definition.config,
    )
    window = tuple(
        Bar(
            symbol="000001.SZ",
            ts=index,
            trade_date=20250100 + index,
            open=Decimal(value),
            high=Decimal(value),
            low=Decimal(value),
            close=Decimal(value),
            volume=1000,
            amount=Decimal(value * 1000),
        )
        for index, value in enumerate(range(10, 30), start=1)
    )

    assert spec.calculator(window) == Decimal("1.9")


def test_legacy_builtin_buy_and_hold_is_migrated_to_full_allocation(tmp_path: Path) -> None:
    store = DefinitionStore(tmp_path / "research.db")
    store.initialize()
    with sqlite3.connect(store.path) as connection:
        connection.execute(
            "UPDATE research_definitions SET code=?, description=?, config_json=?, version=1 "
            "WHERE kind='strategy' AND name='buy_and_hold'",
            (
                LEGACY_BUY_AND_HOLD_CODE,
                "首个可交易信号后买入并持有。",
                json.dumps({"parameters": {"quantity": 1000}}),
            ),
        )

    migrated = store.get("strategy", "buy_and_hold")

    assert migrated.version == 2
    assert migrated.config == {"parameters": {"allocation_ratio": 1.0}}
    assert "尽可能满仓" in migrated.description
