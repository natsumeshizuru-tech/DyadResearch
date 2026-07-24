import sqlite3
from decimal import Decimal

import pytest

from dyadresearch.backtest.engine import BacktestEngine
from dyadresearch.backtest.policy import BacktestPolicy
from dyadresearch.data.catalog import CatalogReader
from dyadresearch.data.compat import LocalXtData
from dyadresearch.data.financial import FinancialReader
from dyadresearch.data.query import MarketDataReader
from dyadresearch.data.sqlite import readonly_connection
from dyadresearch.errors import PointInTimeUnavailableError
from dyadresearch.strategy.examples import LowVolumeRatioMomentumStrategy
from dyadresearch.strategy.inputs import load_capital_schedule, load_previous_closes
from dyadresearch.strategy.universe import build_low_volume_full_market_data


@pytest.mark.integration
def test_real_daily_query_is_sorted_and_repeatable(real_config) -> None:
    reader = MarketDataReader(real_config.data)
    first = reader.query_bars(["000001.SZ"], period="1d", start=20240102, end=20240110)
    second = reader.query_bars(["000001.SZ"], period="1d", start=20240102, end=20240110)
    assert len(first.bars) > 0
    assert first.bars == tuple(sorted(first.bars, key=lambda bar: (bar.ts, bar.symbol)))
    assert first.fingerprint == second.fingerprint


@pytest.mark.integration
def test_real_source_connection_refuses_write(real_config) -> None:
    path = real_config.data.root / real_config.data.daily_bars
    with readonly_connection(path) as connection:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("CREATE TABLE forbidden_write(value INTEGER)")


@pytest.mark.integration
def test_financial_point_in_time_uses_announcement_date(real_config) -> None:
    reader = FinancialReader(real_config.data)
    before = reader.as_of(
        ["000001.SZ"],
        table_names=["Income"],
        as_of_date=20240419,
        earliest_report_date=20240101,
    )
    after = reader.as_of(
        ["000001.SZ"],
        table_names=["Income"],
        as_of_date=20240420,
        earliest_report_date=20240101,
    )
    assert before == ()
    assert [(item.report_date, item.announcement_date) for item in after] == [(20240331, 20240420)]


@pytest.mark.integration
def test_historical_sector_snapshot_is_rejected(real_config) -> None:
    with pytest.raises(PointInTimeUnavailableError, match="no exact snapshot"):
        CatalogReader(real_config.data).sector_members("沪深A股", 20250102)


@pytest.mark.integration
def test_real_minute_query_crosses_month_shards(real_config) -> None:
    result = MarketDataReader(real_config.data).query_bars(
        ["000001.SZ"], period="1m", start=20250731, end=20250801
    )
    assert {bar.trade_date for bar in result.bars} == {20250731, 20250801}
    assert [path.rsplit("\\", 1)[-1] for path in result.paths] == [
        "bars_1m_SZ_202507.db",
        "bars_1m_SZ_202508.db",
    ]


@pytest.mark.integration
def test_local_xtdata_compat_has_expected_shape(real_config) -> None:
    frames = LocalXtData(real_config.data).get_market_data_ex(
        ["time", "close", "volume"],
        ["000001.SZ"],
        period="1d",
        start_time="20240102",
        end_time="20240105",
        fill_data=False,
    )
    frame = frames["000001.SZ"]
    assert list(frame.columns) == ["time", "close", "volume"]
    assert frame.index.name == "stime"
    assert frame.index.is_monotonic_increasing


@pytest.mark.integration
def test_real_low_volume_ratio_momentum_skips_next_minute_limit_up(real_config) -> None:
    symbol = "000920.SZ"
    query = MarketDataReader(real_config.data).query_bars(
        [symbol], period="1m", start=20260701, end=20260717
    )
    strategy = LowVolumeRatioMomentumStrategy(
        symbol,
        capital_schedule=load_capital_schedule(real_config.data, symbol, end=20260717),
        previous_closes=load_previous_closes(real_config.data, symbol, end=20260717),
    )

    result = BacktestEngine().run(
        strategy,
        bars=query.bars,
        data_fingerprint=query.fingerprint,
        policy=BacktestPolicy(initial_cash=Decimal("1000000")),
    )

    signal = next(
        event for event in result.event_log if event["event"] == "low_volume_ratio_signal"
    )
    assert signal["trade_date"] == 20260716
    assert signal["price_gain"] > 0.07
    assert signal["volume_ratio"] < 0.6
    assert signal["market_cap"] < 30_000_000_000
    assert result.trades == ()
    skipped = next(
        event
        for event in result.event_log
        if event.get("reason") == "next_minute_open_at_upper_limit"
    )
    assert skipped["symbol"] == symbol
    assert skipped["opening_price"] == 14.15
    assert result.final_positions == {}


@pytest.mark.integration
def test_real_full_market_low_volume_scan_finds_main_board_signals(real_config) -> None:
    result = build_low_volume_full_market_data(
        real_config.data,
        start=20260716,
        end=20260717,
    )

    assert result.candidate_days > 0
    assert result.scanned_minute_bars > 0
    assert "000920.SZ" in result.symbols
    assert all(signal.market_cap < Decimal("30000000000") for signal in result.signals)
    assert all(signal.price_gain > Decimal("0.07") for signal in result.signals)
    assert all(signal.volume_ratio < Decimal("0.6") for signal in result.signals)
    assert result.bars == tuple(sorted(result.bars, key=lambda bar: (bar.ts, bar.symbol)))
