from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from dyadresearch.config import DataConfig
from dyadresearch.data.sqlite import readonly_connection


def load_capital_schedule(
    config: DataConfig, symbol: str, *, end: int
) -> tuple[tuple[int, Decimal], ...]:
    by_announcement: dict[int, tuple[int, Decimal]] = {}
    pattern = config.fundamentals_pattern.replace("{year}", "*")
    for path in sorted(config.root.glob(pattern)):
        with readonly_connection(path, busy_timeout_ms=config.busy_timeout_ms) as connection:
            rows = connection.execute(
                "SELECT report_date, announcement_date, raw_json FROM financial_records "
                "WHERE symbol=? AND table_name='Capital' AND announcement_date<=? "
                "ORDER BY announcement_date, report_date",
                (symbol.upper(), end),
            ).fetchall()
        for row in rows:
            fields = _decode(str(row[2]))
            shares = fields.get("total_capital")
            if shares is None:
                continue
            value = Decimal(str(shares))
            if value > 0:
                by_announcement[int(row[1])] = (int(row[0]), value)
    return tuple(
        (announcement, value[1]) for announcement, value in sorted(by_announcement.items())
    )


def load_capital_schedules(
    config: DataConfig, symbols: set[str], *, end: int
) -> dict[str, tuple[tuple[int, Decimal], ...]]:
    by_symbol: dict[str, dict[int, tuple[int, Decimal]]] = {}
    pattern = config.fundamentals_pattern.replace("{year}", "*")
    for path in sorted(config.root.glob(pattern)):
        with readonly_connection(path, busy_timeout_ms=config.busy_timeout_ms) as connection:
            rows = connection.execute(
                "SELECT symbol, report_date, announcement_date, raw_json "
                "FROM financial_records WHERE table_name='Capital' AND announcement_date<=? "
                "ORDER BY symbol, announcement_date, report_date",
                (end,),
            )
            for row in rows:
                symbol = str(row[0])
                if symbol not in symbols:
                    continue
                fields = _decode(str(row[3]))
                shares = fields.get("total_capital")
                if shares is None:
                    continue
                value = Decimal(str(shares))
                if value > 0:
                    by_symbol.setdefault(symbol, {})[int(row[2])] = (int(row[1]), value)
    return {
        symbol: tuple((announcement, value[1]) for announcement, value in sorted(schedule.items()))
        for symbol, schedule in by_symbol.items()
    }


def load_previous_closes(config: DataConfig, symbol: str, *, end: int) -> dict[int, Decimal]:
    path = config.root / config.daily_bars
    with readonly_connection(path, busy_timeout_ms=config.busy_timeout_ms) as connection:
        rows = connection.execute(
            "SELECT trade_date, close FROM bars WHERE symbol=? AND trade_date<=? "
            "AND close IS NOT NULL ORDER BY trade_date",
            (symbol.upper(), end),
        ).fetchall()
    previous: Decimal | None = None
    result: dict[int, Decimal] = {}
    for row in rows:
        trade_date = int(row[0])
        if previous is not None:
            result[trade_date] = previous
        previous = Decimal(str(row[1]))
    return result


def _decode(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
