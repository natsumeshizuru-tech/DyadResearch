from __future__ import annotations

from typing import Any

import pandas as pd

from dyadresearch.config import DataConfig
from dyadresearch.data.adjustments import adjust_bars
from dyadresearch.data.aggregation import (
    DAILY_PERIODS,
    DERIVED_PERIODS,
    MINUTE_SIZES,
    aggregate_bars,
)
from dyadresearch.data.catalog import CatalogReader
from dyadresearch.data.models import AdjustmentMode, Bar
from dyadresearch.data.query import MarketDataReader

FIELD_MAP = {
    "time": "ts",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "amount": "amount",
    "settle": "settlement_price",
    "openInterest": "open_interest",
    "preClose": "pre_close",
    "suspendFlag": "suspend_flag",
}
DEFAULT_FIELDS = tuple(FIELD_MAP)


class LocalXtData:
    """Historical subset of XtData backed only by readonly SQLite."""

    def __init__(self, config: DataConfig) -> None:
        self.config = config
        self.market = MarketDataReader(config)
        self.catalog = CatalogReader(config)

    def get_market_data_ex(
        self,
        field_list: list[str] | None = None,
        stock_list: list[str] | None = None,
        period: str = "1d",
        start_time: str = "",
        end_time: str = "",
        count: int = -1,
        dividend_type: AdjustmentMode = "none",
        fill_data: bool = False,
        subscribe: bool = False,
    ) -> dict[str, pd.DataFrame]:
        if subscribe:
            raise ValueError("LocalXtData is historical-only")
        if fill_data:
            raise ValueError("fill_data is disabled to avoid manufacturing observations")
        symbols = sorted({symbol.upper() for symbol in stock_list or []})
        if not symbols:
            return {}
        start = _compact_date(start_time, 19900101)
        end = _compact_date(end_time, 29991231)
        raw_period = "1m" if period in MINUTE_SIZES else "1d" if period in DAILY_PERIODS else period
        result = self.market.query_bars(symbols, period=raw_period, start=start, end=end)
        bars = result.bars
        actions = self.catalog.corporate_actions(symbols, 19900101, end)
        bars = adjust_bars(bars, actions, mode=dividend_type)
        if period in DERIVED_PERIODS:
            bars = aggregate_bars(bars, period)
        fields = field_list or list(DEFAULT_FIELDS)
        output: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            selected = [bar for bar in bars if bar.symbol == symbol]
            if count > 0:
                selected = selected[-count:]
            output[symbol] = _frame(selected, fields)
        return output

    def get_local_data(self, *args: Any, **kwargs: Any) -> dict[str, pd.DataFrame]:
        return self.get_market_data_ex(*args, **kwargs)

    def get_trading_calendar(
        self, market: str, start_time: str = "", end_time: str = ""
    ) -> list[str]:
        return [
            str(day)
            for day in self.catalog.open_days(
                market,
                _compact_date(start_time, 19900101),
                _compact_date(end_time, 29991231),
            )
        ]

    def get_stock_list_in_sector(self, sector_name: str, snapshot_date: int) -> list[str]:
        return list(self.catalog.sector_members(sector_name, snapshot_date))

    def get_instrument_detail(self, stock_code: str, iscomplete: bool = False) -> dict[str, object]:
        del iscomplete
        return self.catalog.instrument(stock_code) or {}

    def get_divid_factors(
        self, stock_code: str, start_time: str = "", end_time: str = ""
    ) -> pd.DataFrame:
        actions = self.catalog.corporate_actions(
            [stock_code.upper()],
            _compact_date(start_time, 19900101),
            _compact_date(end_time, 29991231),
        )
        columns = (
            "interest",
            "stock_bonus",
            "stock_gift",
            "allot_num",
            "allot_price",
            "dr",
        )
        if not actions:
            return pd.DataFrame(columns=columns).rename_axis("action_date")
        rows = [
            {
                "action_date": action.action_date,
                **{column: getattr(action, column) for column in columns},
            }
            for action in actions
        ]
        return pd.DataFrame(rows).set_index("action_date")


def _compact_date(value: str, default: int) -> int:
    digits = "".join(character for character in value if character.isdigit())
    if not digits:
        return default
    if len(digits) < 8:
        raise ValueError(f"date must contain YYYYMMDD: {value}")
    return int(digits[:8])


def _frame(bars: list[Bar], fields: list[str]) -> pd.DataFrame:
    for field in fields:
        if field not in FIELD_MAP:
            raise ValueError(f"unsupported XtData field: {field}")
    rows = [{field: getattr(bar, FIELD_MAP[field]) for field in fields} for bar in bars]
    index = pd.DatetimeIndex(
        pd.to_datetime([bar.ts for bar in bars], unit="ms", utc=True)
        .tz_convert("Asia/Shanghai")
        .tz_localize(None),
        name="stime",
    )
    return pd.DataFrame(rows, index=index, columns=fields)
