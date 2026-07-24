import sqlite3

import pytest

from dyadresearch.config import DataConfig
from dyadresearch.data.capabilities import capability_matrix, require_bar_capability
from dyadresearch.data.shards import bar_paths, months_between, symbol_market
from dyadresearch.errors import DataCapabilityError


def test_months_between_crosses_year() -> None:
    assert months_between(20251231, 20260201) == ("202512", "202601", "202602")


def test_bar_paths_are_pruned_by_market_and_month(tmp_path) -> None:
    config = DataConfig(root=tmp_path)
    paths = bar_paths(config, ["600000.SH", "000001.SZ"], "1m", 20250711, 20250801)
    assert [path.name for path in paths] == [
        "bars_1m_SH_202507.db",
        "bars_1m_SZ_202507.db",
        "bars_1m_SH_202508.db",
        "bars_1m_SZ_202508.db",
    ]


def test_symbol_market_rejects_unknown_suffix() -> None:
    with pytest.raises(ValueError, match="unsupported symbol"):
        symbol_market("AAPL.US")


def test_capability_refuses_missing_minute_history() -> None:
    with pytest.raises(DataCapabilityError, match="truthful local coverage"):
        require_bar_capability("1m", ["000001.SZ"], 20240101, 20250715)


def test_daily_capability_uses_current_sqlite_range(tmp_path) -> None:
    database = tmp_path / "bars_1d.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE bars (trade_date INTEGER NOT NULL)")
        connection.executemany(
            "INSERT INTO bars (trade_date) VALUES (?)", [(20260717,), (20260724,)]
        )

    require_bar_capability("1d", ["000001.SZ"], 20260723, 20260724, data_root=tmp_path)
    daily = next(item for item in capability_matrix(tmp_path) if item["dataset"] == "bars:1d")
    assert daily["available_from"] == 20260717
    assert daily["available_to"] == 20260724
