from time import perf_counter

import pytest

from dyadresearch.data.query import MarketDataReader


@pytest.mark.performance
def test_two_symbol_daily_query_stays_within_interactive_budget(real_config) -> None:
    started = perf_counter()
    result = MarketDataReader(real_config.data).query_bars(
        ["000001.SZ", "600000.SH"], period="1d", start=20240102, end=20241231
    )
    elapsed = perf_counter() - started
    assert len(result.bars) >= 400
    assert elapsed < 5.0
