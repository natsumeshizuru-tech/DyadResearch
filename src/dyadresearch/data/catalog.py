from __future__ import annotations

from decimal import Decimal

from dyadresearch.config import DataConfig
from dyadresearch.data.models import CorporateAction
from dyadresearch.data.sqlite import readonly_connection
from dyadresearch.errors import PointInTimeUnavailableError


class CatalogReader:
    def __init__(self, config: DataConfig) -> None:
        self.config = config
        self.path = config.root / config.catalog

    def instrument(self, symbol: str) -> dict[str, object] | None:
        with readonly_connection(self.path, busy_timeout_ms=self.config.busy_timeout_ms) as con:
            row = con.execute(
                "SELECT * FROM instruments WHERE symbol=?", (symbol.upper(),)
            ).fetchone()
            return None if row is None else dict(row)

    def open_days(self, market: str, start: int, end: int) -> tuple[int, ...]:
        with readonly_connection(self.path, busy_timeout_ms=self.config.busy_timeout_ms) as con:
            return tuple(
                int(row[0])
                for row in con.execute(
                    "SELECT trade_date FROM trading_calendar "
                    "WHERE market=? AND is_open=1 AND trade_date BETWEEN ? AND ? "
                    "ORDER BY trade_date",
                    (market.upper(), start, end),
                )
            )

    def corporate_actions(
        self, symbols: list[str], start: int, end: int
    ) -> tuple[CorporateAction, ...]:
        if not symbols:
            return ()
        placeholders = ",".join("?" for _ in symbols)
        with readonly_connection(self.path, busy_timeout_ms=self.config.busy_timeout_ms) as con:
            rows = con.execute(
                "SELECT ca.symbol, ca.action_date, ca.interest, ca.stock_bonus, "
                "ca.stock_gift, ca.allot_num, ca.allot_price, ca.dr "
                "FROM corporate_actions AS ca "
                "LEFT JOIN instruments AS i ON i.symbol=ca.symbol "
                f"WHERE ca.symbol IN ({placeholders}) "
                "AND ca.action_date BETWEEN ? AND ? "
                "AND (i.list_date IS NULL OR ca.action_date>=i.list_date) "
                "ORDER BY ca.action_date, ca.symbol",
                [*[symbol.upper() for symbol in symbols], start, end],
            ).fetchall()
        return tuple(
            CorporateAction(
                symbol=str(row[0]),
                action_date=int(row[1]),
                interest=Decimal(str(row[2])),
                stock_bonus=Decimal(str(row[3])),
                stock_gift=Decimal(str(row[4])),
                allot_num=Decimal(str(row[5])),
                allot_price=Decimal(str(row[6])),
                dr=Decimal(str(row[7])),
            )
            for row in rows
        )

    def sector_members(self, sector: str, as_of: int) -> tuple[str, ...]:
        snapshot = self._require_exact_snapshot("sector_snapshots", as_of)
        with readonly_connection(self.path, busy_timeout_ms=self.config.busy_timeout_ms) as con:
            return tuple(
                str(row[0])
                for row in con.execute(
                    "SELECT symbol FROM sector_snapshots "
                    "WHERE snapshot_date=? AND sector_name=? ORDER BY symbol",
                    (snapshot, sector),
                )
            )

    def index_weights(self, index_code: str, as_of: int) -> dict[str, Decimal]:
        snapshot = self._require_exact_snapshot("index_weight_snapshots", as_of)
        with readonly_connection(self.path, busy_timeout_ms=self.config.busy_timeout_ms) as con:
            return {
                str(row[0]): Decimal(str(row[1]))
                for row in con.execute(
                    "SELECT symbol, weight FROM index_weight_snapshots "
                    "WHERE snapshot_date=? AND index_code=? ORDER BY symbol",
                    (snapshot, index_code.upper()),
                )
            }

    def _require_exact_snapshot(self, table: str, as_of: int) -> int:
        with readonly_connection(self.path, busy_timeout_ms=self.config.busy_timeout_ms) as con:
            values = [
                int(row[0]) for row in con.execute(f"SELECT DISTINCT snapshot_date FROM {table}")
            ]
        if as_of not in values:
            available = ", ".join(str(value) for value in sorted(values)) or "none"
            raise PointInTimeUnavailableError(
                f"{table} has no exact snapshot for {as_of}; available: {available}"
            )
        return as_of
