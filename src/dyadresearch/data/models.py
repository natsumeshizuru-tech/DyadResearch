from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Literal

Period = Literal["1d", "1m", "5m", "15m", "30m", "1h", "1w", "1mon", "1q", "1hy", "1y"]
AdjustmentMode = Literal["none", "front", "back", "front_ratio", "back_ratio"]


@dataclass(frozen=True, slots=True)
class Bar:
    symbol: str
    ts: int
    trade_date: int
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: int
    amount: Decimal | None
    settlement_price: Decimal | None = None
    open_interest: Decimal | None = None
    pre_close: Decimal | None = None
    suspend_flag: int = 0
    source: str = ""
    ingested_at: int = 0
    source_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CorporateAction:
    symbol: str
    action_date: int
    interest: Decimal
    stock_bonus: Decimal
    stock_gift: Decimal
    allot_num: Decimal
    allot_price: Decimal
    dr: Decimal


@dataclass(frozen=True, slots=True)
class FinancialRecord:
    symbol: str
    table_name: str
    report_date: int
    announcement_date: int
    row_ordinal: int
    values: dict[str, Any]
    source_hash: str


@dataclass(frozen=True, slots=True)
class DataWarning:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class QueryResult:
    bars: tuple[Bar, ...]
    paths: tuple[str, ...]
    warnings: tuple[DataWarning, ...]
    fingerprint: str
