import sqlite3
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from dyadresearch.config import DataConfig, load_config
from dyadresearch.data.adjustments import adjust_bars
from dyadresearch.data.capabilities import require_bar_capability
from dyadresearch.data.compat import LocalXtData, _compact_date
from dyadresearch.data.models import Bar, CorporateAction
from dyadresearch.data.query import MarketDataReader
from dyadresearch.data.sqlite import readonly_connection, require_columns
from dyadresearch.doctor import _database_check, run_doctor
from dyadresearch.errors import ConfigurationError, DataCapabilityError, DataContractError


def test_config_invalid_shapes_and_timeout(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    with pytest.raises(ConfigurationError, match="does not exist"):
        load_config(missing)
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("[]", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="root"):
        load_config(invalid)
    invalid.write_text("project: []\ndata: {}", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="project"):
        load_config(invalid)
    with pytest.raises(ConfigurationError, match="negative"):
        DataConfig(tmp_path, busy_timeout_ms=-1)


def test_doctor_success_missing_and_sqlite_error(real_config, tmp_path: Path) -> None:
    assert run_doctor(real_config)["ok"] is True
    assert _database_check(tmp_path / "missing.db", 1)[0] is False
    invalid = tmp_path / "invalid.db"
    invalid.write_text("not sqlite", encoding="utf-8")
    ok, detail = _database_check(invalid, 1)
    assert ok is False
    assert detail


def test_readonly_and_schema_contract_errors(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError), readonly_connection(tmp_path / "missing.db"):
        pass
    database = tmp_path / "empty.db"
    sqlite3.connect(database).close()
    with (
        readonly_connection(database) as connection,
        pytest.raises(DataContractError, match="missing required table"),
    ):
        require_columns(connection, "bars", {"symbol"})
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE bars(symbol TEXT)")
    with (
        readonly_connection(database) as connection,
        pytest.raises(DataContractError, match="missing columns"),
    ):
        require_columns(connection, "bars", {"symbol", "ts"})


def test_query_non_strict_warnings_and_empty(tmp_path: Path) -> None:
    reader = MarketDataReader(DataConfig(tmp_path))
    assert reader.query_bars([], period="1d", start=20240102, end=20240103).bars == ()
    result = reader.query_bars(
        ["000001.SZ"], period="1m", start=20240101, end=20240102, strict=False
    )
    assert {warning.code for warning in result.warnings} == {
        "RANGE_OUTSIDE_CAPABILITY",
        "MISSING_SHARDS",
    }
    with pytest.raises(FileNotFoundError):
        reader.query_bars(["000001.SZ"], period="1d", start=20240102, end=20240103)


def test_capability_and_compat_validation(real_config) -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        require_bar_capability("1d", [], 20240103, 20240102)
    with pytest.raises(DataCapabilityError, match="unsupported"):
        require_bar_capability("tick", [], 20240102, 20240103)
    compat = LocalXtData(real_config.data)
    assert compat.get_market_data_ex(stock_list=[]) == {}
    with pytest.raises(ValueError, match="historical-only"):
        compat.get_market_data_ex(stock_list=["000001.SZ"], subscribe=True)
    with pytest.raises(ValueError, match="manufacturing"):
        compat.get_market_data_ex(stock_list=["000001.SZ"], fill_data=True)
    with pytest.raises(ValueError, match="YYYYMMDD"):
        _compact_date("2024", 1)


def test_adjustment_additional_modes_and_invalid_denominator() -> None:
    bar = Bar(
        "000001.SZ",
        1,
        20250101,
        Decimal("10"),
        Decimal("10"),
        Decimal("10"),
        Decimal("10"),
        100,
        Decimal("1000"),
    )
    action = CorporateAction(
        "000001.SZ",
        20250102,
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0"),
        Decimal("0.5"),
    )
    assert adjust_bars((bar,), (action,), mode="front_ratio")[0].close == Decimal("20")
    action_on_date = replace(action, action_date=20250101)
    assert adjust_bars((bar,), (action_on_date,), mode="back_ratio")[0].close == Decimal("5.0")
    invalid = replace(action, stock_bonus=Decimal("-2"))
    with pytest.raises(ValueError, match="denominator"):
        adjust_bars((bar,), (invalid,), mode="front")
