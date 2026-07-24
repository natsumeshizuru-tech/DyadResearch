# coding: gbk
"""Big-QMT ContextInfo target-weight executor.

The file is ASCII-only so the declared GBK source encoding is portable.
Live trading is disabled by default. Pure planning functions can be tested
outside QMT without importing a broker SDK.
"""

from __future__ import print_function

import csv
import datetime
import hashlib
import json
import math
import os

try:
    import config_local as CONFIG
except ImportError:
    import config_example as CONFIG

_STATE = {"handled_dates": set(), "targets": None}


def init(ContextInfo):
    _validate_config()
    if hasattr(ContextInfo, "set_account") and CONFIG.ACCOUNT_ID:
        ContextInfo.set_account(CONFIG.ACCOUNT_ID)
    if hasattr(ContextInfo, "set_universe"):
        ContextInfo.set_universe([])
    print("[DyadResearch] initialized live=%s" % bool(CONFIG.ENABLE_LIVE_TRADING))


def handlebar(ContextInfo):
    now = _context_time(ContextInfo)
    trade_date = now.strftime("%Y%m%d")
    if trade_date in _STATE["handled_dates"]:
        return
    if now.strftime("%H:%M:%S") < CONFIG.EXECUTION_TIME:
        return
    targets = load_targets(CONFIG.TARGET_CSV, trade_date)
    snapshot = query_account_snapshot(ContextInfo)
    plan = build_order_plan(
        targets,
        snapshot["total_asset"],
        snapshot["cash"],
        snapshot["holdings"],
        snapshot["available"],
        snapshot["prices"],
        CONFIG,
    )
    write_plan(CONFIG.PLAN_CSV, plan)
    if CONFIG.ENABLE_LIVE_TRADING:
        if not CONFIG.ACCOUNT_ID:
            raise RuntimeError("ACCOUNT_ID is required when live trading is enabled")
        execute_plan(ContextInfo, plan, trade_date)
    else:
        for item in plan:
            print("[DRY-RUN] %s" % json.dumps(item, sort_keys=True))
    _STATE["handled_dates"].add(trade_date)


def load_targets(path, expected_trade_date):
    rows = []
    with open(path, "r") as handle:
        reader = csv.DictReader(handle)
        required = {
            "trade_date",
            "stock_code",
            "target_weight",
            "reference_price",
            "experiment_id",
            "signal_hash",
        }
        if set(reader.fieldnames or []) != required:
            raise ValueError("target CSV columns do not match the required contract")
        for raw in reader:
            if raw["trade_date"].replace("-", "") != expected_trade_date:
                raise ValueError("target trade_date does not match the current session")
            signal_hash = raw["signal_hash"].lower()
            if len(signal_hash) != 64 or any(ch not in "0123456789abcdef" for ch in signal_hash):
                raise ValueError("signal_hash must be a 64-character SHA-256 hex string")
            rows.append(
                {
                    "trade_date": expected_trade_date,
                    "stock_code": raw["stock_code"].upper(),
                    "target_weight": float(raw["target_weight"]),
                    "reference_price": float(raw["reference_price"]),
                    "experiment_id": raw["experiment_id"],
                    "signal_hash": signal_hash,
                }
            )
    validate_targets(rows, CONFIG)
    return rows


def validate_targets(rows, config):
    if not rows:
        raise ValueError("target file is empty")
    symbols = [item["stock_code"] for item in rows]
    if len(symbols) != len(set(symbols)):
        raise ValueError("target file contains duplicate symbols")
    if len(rows) > config.MAX_HOLDINGS:
        raise ValueError("target holdings exceed MAX_HOLDINGS")
    if config.WHITELIST:
        outside = sorted(set(symbols) - set(config.WHITELIST))
        if outside:
            raise ValueError("target contains symbols outside WHITELIST: %s" % outside)
    weights = [item["target_weight"] for item in rows]
    if any(weight < 0 or weight > config.MAX_SINGLE_WEIGHT for weight in weights):
        raise ValueError("target weight violates long-only or single-name limit")
    if abs(sum(weights) - 1.0) > config.WEIGHT_SUM_TOLERANCE:
        raise ValueError("target weights do not sum to one")
    hashes = set(item["signal_hash"] for item in rows)
    experiments = set(item["experiment_id"] for item in rows)
    if len(hashes) != 1 or len(experiments) != 1:
        raise ValueError("one target file must contain one signal hash and experiment ID")


def build_order_plan(targets, total_asset, cash, holdings, available, prices, config):
    del cash  # Cash is checked again after sell-first ordering.
    plan = []
    target_symbols = set(item["stock_code"] for item in targets)
    by_symbol = dict((item["stock_code"], item) for item in targets)
    all_symbols = sorted(target_symbols | set(holdings))
    for symbol in all_symbols:
        row = by_symbol.get(symbol)
        price = float(prices.get(symbol, row["reference_price"] if row else 0))
        if price <= 0:
            raise ValueError("missing positive price for %s" % symbol)
        target_weight = row["target_weight"] if row else 0.0
        target_quantity = int(
            math.floor(target_weight * float(total_asset) / price / config.LOT_SIZE)
            * config.LOT_SIZE
        )
        current = int(holdings.get(symbol, 0))
        difference = target_quantity - current
        if difference < 0:
            sellable = int(available.get(symbol, 0))
            quantity = min(-difference, sellable)
            if quantity > 0:
                plan.append(_plan_row(symbol, "SELL", quantity, price, row, target_weight))
            if quantity < -difference:
                plan.append(
                    _plan_row(
                        symbol,
                        "BLOCKED_T1",
                        -difference - quantity,
                        price,
                        row,
                        target_weight,
                    )
                )
        elif difference > 0:
            quantity = difference // config.LOT_SIZE * config.LOT_SIZE
            if quantity > 0 and quantity * price >= config.MIN_ORDER_NOTIONAL:
                plan.append(_plan_row(symbol, "BUY", quantity, price, row, target_weight))
    executable = [item for item in plan if item["side"] in ("BUY", "SELL")]
    for item in executable:
        if item["notional"] > config.MAX_ORDER_NOTIONAL:
            raise ValueError("order notional exceeds MAX_ORDER_NOTIONAL")
    turnover = sum(item["notional"] for item in executable) / float(total_asset)
    if turnover > config.MAX_DAILY_TURNOVER:
        raise ValueError("planned turnover exceeds MAX_DAILY_TURNOVER")
    priority = {"SELL": 0, "BUY": 1}
    plan.sort(key=lambda item: (priority.get(item["side"], 2), item["stock_code"]))
    return plan


def _plan_row(symbol, side, quantity, price, target, target_weight):
    experiment_id = target["experiment_id"] if target else ""
    signal_hash = target["signal_hash"] if target else ""
    identity = "%s|%s|%s|%s" % (experiment_id, signal_hash, symbol, side)
    return {
        "stock_code": symbol,
        "side": side,
        "quantity": int(quantity),
        "reference_price": float(price),
        "notional": float(price) * int(quantity),
        "target_weight": float(target_weight),
        "experiment_id": experiment_id,
        "signal_hash": signal_hash,
        "user_order_id": hashlib.sha256(identity.encode("ascii")).hexdigest()[:24],
    }


def query_account_snapshot(ContextInfo):
    api = _api("get_trade_detail_data")
    if api is None:
        raise RuntimeError("get_trade_detail_data is unavailable outside Big QMT")
    account_rows = api(CONFIG.ACCOUNT_ID, CONFIG.ACCOUNT_TYPE, "account", ContextInfo)
    position_rows = api(CONFIG.ACCOUNT_ID, CONFIG.ACCOUNT_TYPE, "position", ContextInfo)
    if not account_rows:
        raise RuntimeError("account query returned no rows")
    account = account_rows[0]
    total_asset = float(_field(account, ("m_dBalance", "m_dAssureAsset", "total_asset"), 0))
    cash = float(_field(account, ("m_dAvailable", "available_cash"), 0))
    holdings = {}
    available = {}
    prices = {}
    for row in position_rows or []:
        symbol = str(_field(row, ("m_strInstrumentID", "stock_code"), "")).upper()
        holdings[symbol] = int(_field(row, ("m_nVolume", "quantity"), 0))
        available[symbol] = int(_field(row, ("m_nCanUseVolume", "available"), 0))
        prices[symbol] = float(_field(row, ("m_dLastPrice", "last_price"), 0))
    return {
        "total_asset": total_asset,
        "cash": cash,
        "holdings": holdings,
        "available": available,
        "prices": prices,
    }


def execute_plan(ContextInfo, plan, trade_date):
    normal = _api("passorder")
    smart = _api("smart_algo_passorder")
    for item in plan:
        if item["side"] not in ("BUY", "SELL"):
            print("[BLOCKED] %s" % json.dumps(item, sort_keys=True))
            continue
        operation = 23 if item["side"] == "BUY" else 24
        remark = "%s:%s" % (CONFIG.STRATEGY_NAME, item["user_order_id"])
        if CONFIG.ALGORITHM in ("TWAP", "VWAP"):
            if smart is None:
                raise RuntimeError("smart_algo_passorder is unavailable")
            smart(
                operation,
                CONFIG.ACCOUNT_TYPE,
                CONFIG.ACCOUNT_ID,
                item["stock_code"],
                CONFIG.ALGORITHM,
                item["quantity"],
                CONFIG.ALGO_START_TIME,
                CONFIG.ALGO_END_TIME,
                CONFIG.PARTICIPATION_RATE,
                CONFIG.QUICK_TRADE,
                remark,
                ContextInfo,
            )
        else:
            if normal is None:
                raise RuntimeError("passorder is unavailable")
            normal(
                operation,
                1101,
                CONFIG.ACCOUNT_ID,
                item["stock_code"],
                5,
                -1,
                item["quantity"],
                CONFIG.STRATEGY_NAME,
                int(CONFIG.QUICK_TRADE),
                item["user_order_id"],
                ContextInfo,
            )
        print("[SUBMITTED %s] %s" % (trade_date, remark))


def write_plan(path, plan):
    columns = [
        "stock_code",
        "side",
        "quantity",
        "reference_price",
        "notional",
        "target_weight",
        "experiment_id",
        "signal_hash",
        "user_order_id",
    ]
    with open(path, "w") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(plan)


def _context_time(ContextInfo):
    if hasattr(ContextInfo, "get_bar_timetag"):
        value = str(ContextInfo.get_bar_timetag(ContextInfo.barpos))
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) >= 14:
            return datetime.datetime.strptime(digits[:14], "%Y%m%d%H%M%S")
    return datetime.datetime.now()


def _field(value, names, default):
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _api(name):
    return globals().get(name)


def _validate_config():
    if CONFIG.QUICK_TRADE not in (0, 1):
        raise ValueError("QUICK_TRADE must be 0 or 1; value 2 is prohibited")
    if CONFIG.ALGORITHM not in ("NORMAL", "TWAP", "VWAP"):
        raise ValueError("ALGORITHM must be NORMAL, TWAP, or VWAP")
    if CONFIG.ENABLE_LIVE_TRADING and not CONFIG.ACCOUNT_ID:
        raise ValueError("ACCOUNT_ID is required for live trading")
