from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from collections.abc import Callable
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any, Literal, cast

from fastapi import FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from dyadresearch.backtest.engine import BacktestEngine
from dyadresearch.backtest.policy import get_policy
from dyadresearch.config import ResearchConfig, load_config
from dyadresearch.data.adjustments import adjust_bars
from dyadresearch.data.capabilities import capability_matrix
from dyadresearch.data.catalog import CatalogReader
from dyadresearch.data.models import Bar, CorporateAction
from dyadresearch.data.periods import query_period_bars
from dyadresearch.data.query import MarketDataReader
from dyadresearch.data.sqlite import readonly_connection
from dyadresearch.data.xtdata import XtDataBridge
from dyadresearch.doctor import run_doctor
from dyadresearch.errors import DyadResearchError
from dyadresearch.experiments.definitions import DefinitionStore
from dyadresearch.experiments.editor import DefinitionEditor
from dyadresearch.experiments.store import ExperimentStore
from dyadresearch.experiments.workflow import WorkflowRecorder, WorkflowStatus, WorkflowStore
from dyadresearch.factors.evaluator import FactorEvaluator
from dyadresearch.factors.expression import factor_spec_from_definition
from dyadresearch.factors.preprocessing import preprocess_factor_result
from dyadresearch.releases import ReleaseOptions, export_experiment_release, release_receipt
from dyadresearch.reporting.builder import ReportBuilder
from dyadresearch.strategy.examples import (
    BuyAndHoldStrategy,
    FullMarketLowVolumeRatioMomentumStrategy,
    LowVolumeRatioMomentumStrategy,
    MovingAverageCrossStrategy,
)
from dyadresearch.strategy.inputs import load_capital_schedule, load_previous_closes
from dyadresearch.strategy.sdk import Strategy
from dyadresearch.strategy.universe import (
    build_low_volume_full_market_data,
    main_board_limit_ratios,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "research.yaml"
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
ResearchPeriod = Literal["1d", "1m", "5m", "15m", "30m", "1h", "1w", "1mon", "1q", "1hy", "1y"]


class FactorRunRequest(BaseModel):
    name: str = "momentum_20"
    symbol: str = "000001.SZ"
    period: ResearchPeriod = "1d"
    start: int = 20240102
    end: int = 20260717
    winsorize: bool = True
    winsorize_limits: float = Field(default=0.01, ge=0, le=0.25)
    standardize: bool = True
    direction: Literal["high", "low"] = "high"


class BacktestRunRequest(BaseModel):
    strategy: str = Field(default="moving_average_cross", pattern=r"^[a-z][a-z0-9_]{2,63}$")
    symbol: str = "000001.SZ"
    benchmark_symbol: str = "510300.SH"
    period: ResearchPeriod = "1d"
    start: int = 20240102
    end: int = 20260717
    policy: Literal["strict_research", "qmt_compat", "legacy_compare"] = "strict_research"
    initial_cash: Decimal = Field(default=Decimal("1000000"), gt=0)
    quantity: int = Field(default=1000, ge=100)
    fast: int = Field(default=5, ge=1)
    slow: int = Field(default=20, ge=2)
    commission_rate: Decimal = Field(default=Decimal("0.0001"), ge=0, le=Decimal("0.05"))
    minimum_commission: Decimal = Field(default=Decimal("5"), ge=0, le=Decimal("1000"))
    stamp_duty_rate: Decimal = Field(default=Decimal("0.0005"), ge=0, le=Decimal("0.05"))
    universe_mode: Literal["single", "all_market"] = "single"


class DefinitionWriteRequest(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    code: str = Field(min_length=20, max_length=50_000)


class XtDataDownloadRequest(BaseModel):
    dataset: Literal[
        "history",
        "financial",
        "sector",
        "history_contracts",
        "holiday",
        "convertible_bond",
        "etf",
        "index_weight",
    ] = "history"
    symbols: list[str] = Field(default_factory=lambda: ["000001.SZ"], max_length=500)
    period: str = Field(default="1d", min_length=1, max_length=64)
    start_date: str = Field(default="20240101", pattern=r"^$|^\d{8}$")
    end_date: str = Field(default="", pattern=r"^$|^\d{8}$")
    tables: list[str] = Field(default_factory=list, max_length=32)
    import_to_shared_store: bool = True


def _default_release_markets() -> list[Literal["SH", "SZ", "BJ"]]:
    return ["SH", "SZ"]


class ReleaseExportRequest(BaseModel):
    experiment_id: int = Field(gt=0)
    source_commit: str = Field(default="UNCOMMITTED", pattern=r"^(UNCOMMITTED|[0-9a-f]{7,64})$")
    runtime_api_version: str = Field(default="1.0", pattern=r"^[0-9]+\.[0-9]+$")
    approval_status: Literal[
        "draft",
        "candidate",
        "reviewed",
        "paper_approved",
        "qmt_sim_approved",
        "live_candidate",
        "live_approved",
    ] = "draft"
    allowed_markets: list[Literal["SH", "SZ", "BJ"]] = Field(
        default_factory=_default_release_markets, min_length=1
    )
    limitations: list[str] = Field(
        default_factory=lambda: ["Historical research does not guarantee future performance."],
        min_length=1,
    )
    max_position_weight: Decimal = Field(default=Decimal("0.20"), gt=0, le=1)
    max_gross_exposure: Decimal = Field(default=Decimal("0.80"), gt=0, le=1)
    max_daily_turnover: Decimal = Field(default=Decimal("1.00"), ge=0, le=10)
    max_order_notional: Decimal = Field(default=Decimal("10000"), gt=0)


app = FastAPI(
    title="DyadResearch API",
    version="0.1.0",
    description="Read-only local research API backed by migrated SQLite data.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4173", "http://127.0.0.1:4173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


def _config() -> ResearchConfig:
    path = Path(os.environ.get("DYADRESEARCH_CONFIG", DEFAULT_CONFIG))
    return load_config(path)


def _store(config: ResearchConfig) -> ExperimentStore:
    database = config.research.database
    if not database.is_absolute():
        database = PROJECT_ROOT / database
    return ExperimentStore(database)


def _workflow_store(config: ResearchConfig) -> WorkflowStore:
    database = config.research.database
    if not database.is_absolute():
        database = PROJECT_ROOT / database
    return WorkflowStore(database)


def _workflow_artifact_root(config: ResearchConfig) -> Path:
    root = config.research.reports_root
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    return root / "workflows"


def _run_recorded_workflow(
    config: ResearchConfig,
    *,
    experiment_name: str,
    recorder_name: str,
    params: dict[str, Any],
    operation: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    with WorkflowRecorder(
        _workflow_store(config),
        artifact_root=_workflow_artifact_root(config),
        experiment_name=experiment_name,
        recorder_name=recorder_name,
        params=params,
        tags={"surface": "web", "project": "DyadResearch"},
    ) as recorder:
        result = operation()
        recorder.log_metrics(**_workflow_metrics(result))
        recorder.set_tags(
            result_hash=str(result.get("result_hash", "")),
            data_fingerprint=str(result.get("data_fingerprint", "")),
        )
        recorder.save_object("result.json", result)
        experiment_id = int(result["experiment_id"])
        recorder.finish(result_experiment_id=experiment_id)
        return result


def _workflow_metrics(result: dict[str, Any]) -> dict[str, int | float]:
    metrics: dict[str, int | float] = {}
    for prefix, candidate in (
        ("", result),
        ("summary.", result.get("summary")),
        ("metrics.", result.get("metrics")),
    ):
        if not isinstance(candidate, dict):
            continue
        for key, value in candidate.items():
            if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
                continue
            metrics[f"{prefix}{key}"] = float(value) if isinstance(value, Decimal) else value
    return metrics


def _definition_store(config: ResearchConfig) -> DefinitionStore:
    database = config.research.database
    if not database.is_absolute():
        database = PROJECT_ROOT / database
    return DefinitionStore(database)


def _definition_editor(config: ResearchConfig) -> DefinitionEditor:
    return DefinitionEditor(_definition_store(config), PROJECT_ROOT / "workspace")


def _xtdata_bridge() -> XtDataBridge:
    return XtDataBridge()


def _safe[T](callable_: Callable[[], T]) -> T:
    try:
        return callable_()
    except (DyadResearchError, FileNotFoundError, KeyError, ValueError, sqlite3.Error) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/health")
def health() -> dict[str, Any]:
    config = _config()
    doctor = run_doctor(config)
    databases = sorted(config.data.root.glob("*.db"))
    capabilities = capability_matrix(config.data.root)
    daily = next((item for item in capabilities if item["dataset"] == "bars:1d"), None)
    return {
        "ok": doctor["ok"],
        "project": config.name,
        "timezone": config.timezone,
        "data_root": str(config.data.root),
        "database_count": len(databases),
        "data_through": daily["available_to"] if daily is not None else None,
        "readonly": config.data.readonly,
        "checks": doctor["checks"],
        "capabilities": capabilities,
    }


@app.get("/api/capabilities")
def capabilities() -> dict[str, Any]:
    config = _config()
    return {"capabilities": capability_matrix(config.data.root)}


@app.get("/api/xtdata/catalog")
def xtdata_catalog() -> dict[str, Any]:
    return _safe(lambda: _xtdata_bridge().catalog())


@app.post("/api/xtdata/download")
def xtdata_download(request: XtDataDownloadRequest) -> dict[str, Any]:
    payload = request.model_dump(mode="json")
    payload["symbols"] = list(
        dict.fromkeys(str(symbol).strip().upper() for symbol in request.symbols if symbol.strip())
    )
    return _safe(lambda: _xtdata_bridge().download(payload))


@app.get("/api/instruments")
def instruments(
    search: str = "",
    market: str | None = None,
    instrument_type: Literal["all", "stock", "etf"] = "all",
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    config = _config()
    path = config.data.root / config.data.catalog
    conditions = ["instrument_type IN ('stock','etf')"]
    params: list[object] = []
    if instrument_type != "all":
        conditions.append("instrument_type=?")
        params.append(instrument_type)
    if search.strip():
        token = f"%{search.strip().upper()}%"
        conditions.append("(UPPER(symbol) LIKE ? OR UPPER(code) LIKE ? OR name LIKE ?)")
        params.extend((token, token, f"%{search.strip()}%"))
    if market:
        conditions.append("market=?")
        params.append(market.upper())
    sql = (
        "SELECT symbol, code, market, name, instrument_type, list_date, delist_date, is_active "
        "FROM instruments WHERE "
        + " AND ".join(conditions)
        + " ORDER BY is_active DESC, symbol LIMIT ?"
    )
    params.append(limit)

    def query() -> list[dict[str, Any]]:
        with readonly_connection(path, busy_timeout_ms=config.data.busy_timeout_ms) as connection:
            return [dict(row) for row in connection.execute(sql, params)]

    values = _safe(query)
    return {"count": len(values), "instruments": values}


@app.get("/api/bars")
def bars(
    symbol: str = "000001.SZ",
    period: ResearchPeriod = "1d",
    start: int = 20100104,
    end: int = 20260717,
    limit: int = Query(default=2000, ge=1, le=10000),
) -> dict[str, Any]:
    config = _config()

    def query() -> dict[str, Any]:
        result = query_period_bars(
            MarketDataReader(config.data), [symbol.upper()], period=period, start=start, end=end
        )
        selected = result.bars[-limit:]
        return {
            "rows": len(result.bars),
            "returned": len(selected),
            "paths": result.paths,
            "warnings": [asdict(item) for item in result.warnings],
            "fingerprint": result.fingerprint,
            "bars": [bar.to_dict() for bar in selected],
        }

    return cast(dict[str, Any], jsonable_encoder(_safe(query)))


@app.get("/api/data/coverage")
def data_coverage() -> dict[str, Any]:
    config = _config()
    catalog_path = config.data.root / config.data.catalog

    def query() -> dict[str, Any]:
        with readonly_connection(
            catalog_path, busy_timeout_ms=config.data.busy_timeout_ms
        ) as connection:
            instruments = [
                dict(row)
                for row in connection.execute(
                    "SELECT COALESCE(instrument_type, 'unknown') AS instrument_type, "
                    "COUNT(*) AS count, SUM(is_active) AS active_count "
                    "FROM instruments GROUP BY instrument_type ORDER BY instrument_type"
                )
            ]
            market_data = [
                dict(row)
                for row in connection.execute(
                    "SELECT w.dataset, w.period, "
                    "COALESCE(i.instrument_type, 'unknown') AS instrument_type, "
                    "COUNT(*) AS symbols, MIN(w.first_ts) AS first_ts, "
                    "MAX(w.last_ts) AS last_ts, SUM(w.row_count) AS rows "
                    "FROM dataset_watermarks AS w "
                    "LEFT JOIN instruments AS i ON i.symbol=w.symbol "
                    "GROUP BY w.dataset, w.period, instrument_type "
                    "ORDER BY w.dataset, w.period, instrument_type"
                )
            ]
            sector_summary = _reference_summary(connection, "sector_catalog", "sector_name")
            index_summary = _reference_summary(connection, "index_weight_catalog", "index_code")

        financials: list[dict[str, Any]] = []
        database_pattern = config.data.fundamentals_pattern.replace("{year}", "*")
        for path in sorted(config.data.root.glob(database_pattern)):
            with readonly_connection(
                path, busy_timeout_ms=config.data.busy_timeout_ms
            ) as connection:
                row = connection.execute(
                    "SELECT COUNT(*) AS rows, COUNT(DISTINCT symbol) AS symbols, "
                    "MIN(report_date) AS first_report_date, "
                    "MAX(report_date) AS last_report_date, "
                    "COUNT(DISTINCT table_name) AS table_count "
                    "FROM financial_records"
                ).fetchone()
                table_rows = [
                    dict(item)
                    for item in connection.execute(
                        "SELECT table_name, COUNT(*) AS rows, "
                        "COUNT(DISTINCT symbol) AS symbols "
                        "FROM financial_records GROUP BY table_name ORDER BY table_name"
                    )
                ]
            year = int(path.stem.rsplit("_", 1)[-1])
            financials.append({"year": year, **dict(row), "tables": table_rows})
        return {
            "instruments": instruments,
            "market_data": market_data,
            "financials": financials,
            "references": {"sectors": sector_summary, "index_weights": index_summary},
            "capabilities": capability_matrix(config.data.root),
        }

    return cast(dict[str, Any], jsonable_encoder(_safe(query)))


@app.get("/api/financials")
def financials(
    symbol: str = "000001.SZ",
    table_name: str | None = None,
    start: int = 20240101,
    end: int = 20260717,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    config = _config()

    def query() -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        available_tables: set[str] = set()
        start_year, end_year = start // 10000, end // 10000
        for year in range(start_year, end_year + 1):
            path = config.data.root / config.data.fundamentals_pattern.format(year=year)
            if not path.is_file():
                continue
            conditions = ["symbol=?", "report_date BETWEEN ? AND ?"]
            params: list[object] = [symbol.upper(), start, end]
            if table_name:
                conditions.append("table_name=?")
                params.append(table_name)
            with readonly_connection(
                path, busy_timeout_ms=config.data.busy_timeout_ms
            ) as connection:
                available_tables.update(
                    str(row[0])
                    for row in connection.execute(
                        "SELECT DISTINCT table_name FROM financial_records WHERE symbol=?",
                        (symbol.upper(),),
                    )
                )
                rows = connection.execute(
                    "SELECT symbol, table_name, report_date, announcement_date, "
                    "row_ordinal, raw_json, source, source_hash "
                    "FROM financial_records WHERE "
                    + " AND ".join(conditions)
                    + " ORDER BY report_date DESC, announcement_date DESC, row_ordinal "
                    "LIMIT ?",
                    [*params, limit],
                ).fetchall()
            for row in rows:
                item = dict(row)
                item["fields"] = _decode_json(str(item.pop("raw_json")))
                records.append(item)
        records.sort(
            key=lambda item: (
                int(item["report_date"]),
                int(item["announcement_date"]),
                -int(item["row_ordinal"]),
            ),
            reverse=True,
        )
        selected = records[:limit]
        return {
            "symbol": symbol.upper(),
            "table_name": table_name,
            "available_tables": sorted(available_tables),
            "rows": len(records),
            "returned": len(selected),
            "records": selected,
        }

    return cast(dict[str, Any], jsonable_encoder(_safe(query)))


@app.get("/api/reference/sectors")
def reference_sectors(
    search: str = "",
    sector_name: str | None = None,
    snapshot_date: int | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    return _reference_payload(
        table_catalog="sector_catalog",
        table_snapshots="sector_snapshots",
        key="sector_name",
        search=search,
        selected_key=sector_name,
        snapshot_date=snapshot_date,
        limit=limit,
    )


@app.get("/api/reference/index-weights")
def reference_index_weights(
    search: str = "",
    index_code: str | None = None,
    snapshot_date: int | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    return _reference_payload(
        table_catalog="index_weight_catalog",
        table_snapshots="index_weight_snapshots",
        key="index_code",
        search=search,
        selected_key=index_code.upper() if index_code else None,
        snapshot_date=snapshot_date,
        limit=limit,
    )


@app.get("/api/factors")
def factors() -> dict[str, Any]:
    definitions = _definition_store(_config()).list("factor")
    return {
        "factors": [
            {
                **definition.to_dict(),
                "input_fields": definition.config["input_fields"],
                "lookback": definition.config["lookback"],
                "frequency": definition.config["frequency"],
                "higher_is_better": definition.config["higher_is_better"],
            }
            for definition in definitions
        ]
    }


@app.post("/api/factors")
def create_factor(request: DefinitionWriteRequest) -> dict[str, Any]:
    definition = _safe(
        lambda: _definition_store(_config()).create("factor", request.name, request.code)
    )
    return {"factor": definition.to_dict()}


@app.put("/api/factors/{name}")
def update_factor(name: str, request: DefinitionWriteRequest) -> dict[str, Any]:
    if request.name != name:
        raise HTTPException(status_code=400, detail="factor name cannot be changed during update")
    definition = _safe(lambda: _definition_store(_config()).update("factor", name, request.code))
    return {"factor": definition.to_dict()}


@app.delete("/api/factors/{name}")
def delete_factor(name: str) -> dict[str, Any]:
    _safe(lambda: _definition_store(_config()).delete("factor", name))
    return {"deleted": name}


@app.post("/api/factors/{name}/open-editor")
def open_factor_editor(name: str) -> dict[str, Any]:
    return _safe(lambda: _definition_editor(_config()).open("factor", name))


@app.post("/api/factors/{name}/sync-editor")
def sync_factor_editor(name: str) -> dict[str, Any]:
    return _safe(lambda: _definition_editor(_config()).sync("factor", name))


@app.post("/api/factors/run")
def run_factor(request: FactorRunRequest) -> dict[str, Any]:
    config = _config()

    def execute() -> dict[str, Any]:
        definition = _definition_store(config).get("factor", request.name)
        spec = factor_spec_from_definition(
            name=definition.name,
            version=definition.version,
            description=definition.description,
            config=definition.config,
        )
        if request.period != spec.frequency:
            raise ValueError(f"factor {request.name} requires period {spec.frequency}")
        query = query_period_bars(
            MarketDataReader(config.data),
            [request.symbol.upper()],
            period=request.period,
            start=request.start,
            end=request.end,
        )
        raw_result = FactorEvaluator().evaluate(
            spec, query.bars, data_fingerprint=query.fingerprint
        )
        result = preprocess_factor_result(
            raw_result,
            winsorize=request.winsorize,
            winsorize_limits=request.winsorize_limits,
            standardize=request.standardize,
            direction=request.direction,
        )
        record = _store(config).save(
            kind="factor",
            name=spec.name,
            result_hash=result.result_hash,
            data_fingerprint=query.fingerprint,
            config=request.model_dump(),
            result=asdict(result),
        )
        return {
            "experiment_id": record.id,
            "name": result.name,
            "version": result.version,
            "coverage_ratio": result.coverage_ratio,
            "summary": result.summary,
            "result_hash": result.result_hash,
            "data_fingerprint": result.data_fingerprint,
            "preprocessing": {
                "winsorize": request.winsorize,
                "winsorize_limits": request.winsorize_limits,
                "standardize": request.standardize,
                "direction": request.direction,
            },
            "observations": [asdict(item) for item in result.observations],
        }

    return cast(
        dict[str, Any],
        jsonable_encoder(
            _safe(
                lambda: _run_recorded_workflow(
                    config,
                    experiment_name="factor-research",
                    recorder_name=request.name,
                    params=request.model_dump(),
                    operation=execute,
                )
            )
        ),
    )


@app.get("/api/strategies")
def strategies() -> dict[str, Any]:
    return {
        "strategies": [
            definition.to_dict() for definition in _definition_store(_config()).list("strategy")
        ],
        "policies": ["strict_research", "qmt_compat", "legacy_compare"],
    }


@app.post("/api/strategies")
def create_strategy(request: DefinitionWriteRequest) -> dict[str, Any]:
    definition = _safe(
        lambda: _definition_store(_config()).create("strategy", request.name, request.code)
    )
    return {"strategy": definition.to_dict()}


@app.put("/api/strategies/{name}")
def update_strategy(name: str, request: DefinitionWriteRequest) -> dict[str, Any]:
    if request.name != name:
        raise HTTPException(status_code=400, detail="strategy name cannot be changed during update")
    definition = _safe(lambda: _definition_store(_config()).update("strategy", name, request.code))
    return {"strategy": definition.to_dict()}


@app.delete("/api/strategies/{name}")
def delete_strategy(name: str) -> dict[str, Any]:
    _safe(lambda: _definition_store(_config()).delete("strategy", name))
    return {"deleted": name}


@app.post("/api/strategies/{name}/open-editor")
def open_strategy_editor(name: str) -> dict[str, Any]:
    return _safe(lambda: _definition_editor(_config()).open("strategy", name))


@app.post("/api/strategies/{name}/sync-editor")
def sync_strategy_editor(name: str) -> dict[str, Any]:
    return _safe(lambda: _definition_editor(_config()).sync("strategy", name))


@app.post("/api/backtests/run")
def run_backtest(request: BacktestRunRequest) -> dict[str, Any]:
    config = _config()

    def execute() -> dict[str, Any]:
        symbol = request.symbol.upper()
        definition = _definition_store(config).get("strategy", request.strategy)
        parameters = definition.config.get("parameters", {})
        if not isinstance(parameters, dict):
            raise ValueError("strategy parameters are invalid")
        if definition.implementation == "moving_average_cross" and request.fast >= request.slow:
            raise ValueError("fast must be lower than slow")
        if definition.implementation == "low_volume_ratio_momentum" and request.period != "1m":
            raise ValueError("low-volume momentum strategy requires 1-minute bars")
        if (
            request.universe_mode == "all_market"
            and definition.implementation != "low_volume_ratio_momentum"
        ):
            raise ValueError("all-market selection is only supported by selection strategies")
        default_allocation = "1" if definition.implementation == "buy_and_hold" else "0.20"
        allocation_ratio = Decimal(str(parameters.get("allocation_ratio", default_allocation)))
        max_positions = int(parameters.get("max_positions", 5))

        strategy: Strategy
        universe_payload: dict[str, Any]
        research_symbols: tuple[str, ...]
        if request.universe_mode == "all_market":
            universe = build_low_volume_full_market_data(
                config.data,
                start=request.start,
                end=request.end,
                market_cap_max=Decimal(str(parameters.get("market_cap_max", 30_000_000_000))),
                rise_threshold=Decimal(str(parameters.get("rise_threshold", "0.07"))),
                volume_ratio_max=Decimal(str(parameters.get("volume_ratio_max", "0.6"))),
                volume_lookback_days=int(parameters.get("volume_lookback_days", 5)),
            )
            if not universe.bars or not universe.signals:
                raise ValueError(
                    "full-market scan found no tradable minute signal; "
                    f"daily candidates={universe.candidate_days}, "
                    f"minute bars scanned={universe.scanned_minute_bars}"
                )
            research_bars = universe.bars
            research_fingerprint = universe.fingerprint
            research_symbols = universe.symbols
            strategy = FullMarketLowVolumeRatioMomentumStrategy(
                universe.signals,
                allocation_ratio=allocation_ratio,
                max_positions=max_positions,
            )
            universe_payload = {
                "mode": "all_market",
                "universe": "sh_sz_main_board",
                "candidate_days": universe.candidate_days,
                "scanned_minute_bars": universe.scanned_minute_bars,
                "signal_count": len(universe.signals),
                "signal_symbols": list(universe.symbols),
                "source_paths": list(universe.paths),
                "allocation_ratio": float(allocation_ratio),
                "max_positions": max_positions,
            }
        else:
            query = query_period_bars(
                MarketDataReader(config.data),
                [symbol],
                period=request.period,
                start=request.start,
                end=request.end,
            )
            if not query.bars:
                raise ValueError(f"research symbol has no local bars: {symbol}")
            research_bars = query.bars
            research_fingerprint = query.fingerprint
            research_symbols = (symbol,)
            universe_payload = {
                "mode": "single",
                "universe": symbol,
                "candidate_days": 0,
                "scanned_minute_bars": len(query.bars),
                "signal_count": 0,
                "signal_symbols": [symbol],
                "source_paths": list(query.paths),
            }
            if definition.implementation == "buy_and_hold":
                strategy = BuyAndHoldStrategy(
                    symbol,
                    allocation_ratio=allocation_ratio,
                )
            elif definition.implementation == "moving_average_cross":
                strategy = MovingAverageCrossStrategy(
                    symbol, fast=request.fast, slow=request.slow, quantity=request.quantity
                )
            else:
                strategy = LowVolumeRatioMomentumStrategy(
                    symbol,
                    capital_schedule=load_capital_schedule(config.data, symbol, end=request.end),
                    previous_closes=load_previous_closes(config.data, symbol, end=request.end),
                    market_cap_max=Decimal(str(parameters.get("market_cap_max", 30_000_000_000))),
                    rise_threshold=Decimal(str(parameters.get("rise_threshold", "0.07"))),
                    volume_ratio_max=Decimal(str(parameters.get("volume_ratio_max", "0.6"))),
                    volume_lookback_days=int(parameters.get("volume_lookback_days", 5)),
                    allocation_ratio=allocation_ratio,
                    limit_ratio=main_board_limit_ratios(
                        config.data, start=request.start, end=request.end
                    ).get(symbol, Decimal("0.10")),
                )

        benchmark_symbol = request.benchmark_symbol.upper()
        if request.universe_mode == "single" and benchmark_symbol == symbol:
            raise ValueError("benchmark_symbol must differ from the research symbol")
        benchmark_query = query_period_bars(
            MarketDataReader(config.data),
            [benchmark_symbol],
            period=request.period,
            start=request.start,
            end=request.end,
        )
        if not benchmark_query.bars:
            raise ValueError(f"benchmark ETF has no local bars: {benchmark_symbol}")
        catalog = CatalogReader(config.data)
        all_actions = catalog.corporate_actions(
            sorted({*research_symbols, benchmark_symbol}), request.start, request.end
        )
        actions = tuple(action for action in all_actions if action.symbol in set(research_symbols))
        benchmark_actions = tuple(
            action for action in all_actions if action.symbol == benchmark_symbol
        )
        benchmark_total_return_bars = _total_return_benchmark_bars(
            benchmark_query.bars, benchmark_actions
        )
        aligned_start_ts = max(research_bars[0].ts, benchmark_query.bars[0].ts)
        research_bars = tuple(bar for bar in research_bars if bar.ts >= aligned_start_ts)
        benchmark_bars = tuple(
            bar for bar in benchmark_total_return_bars if bar.ts >= aligned_start_ts
        )
        if not research_bars or not benchmark_bars:
            raise ValueError("research symbol and benchmark ETF have no overlapping bars")
        policy = get_policy(
            request.policy,
            initial_cash=request.initial_cash,
            commission_rate=request.commission_rate,
            minimum_commission=request.minimum_commission,
            stamp_duty_rate=request.stamp_duty_rate,
        )
        combined_fingerprint = hashlib.sha256(
            (
                f"{research_fingerprint}:{benchmark_query.fingerprint}:"
                f"adjustment-v1:{_corporate_action_fingerprint(all_actions)}"
            ).encode()
        ).hexdigest()
        result = BacktestEngine().run(
            strategy,
            bars=research_bars,
            data_fingerprint=combined_fingerprint,
            policy=policy,
            corporate_actions=actions,
        )
        result_payload = result.to_dict()
        universe_payload["limit_up_skipped"] = sum(
            1
            for event in result_payload.get("event_log", [])
            if event.get("reason") == "next_minute_open_at_upper_limit"
        )
        universe_payload["unavailable_open_skipped"] = sum(
            1
            for event in result_payload.get("event_log", [])
            if event.get("reason") == "next_minute_open_unavailable"
        )
        universe_payload["position_limit_skipped"] = sum(
            1
            for event in result_payload.get("event_log", [])
            if event.get("reason") == "portfolio_position_limit"
        )
        result_payload["strategy_definition"] = {
            "name": definition.name,
            "title": definition.title,
            "version": definition.version,
            "implementation": definition.implementation,
        }
        result_payload["benchmark_symbol"] = benchmark_symbol
        result_payload["adjustment"] = {
            "execution_price_mode": "none",
            "portfolio_action_mode": "cash_and_share_events",
            "benchmark_price_mode": "front_ratio",
            "research_action_count": len(actions),
            "benchmark_action_count": len(benchmark_actions),
            "lookahead_safe": True,
        }
        if definition.implementation == "buy_and_hold":
            entry_trades = tuple(trade for trade in result.trades if trade.side.value == "buy")
            entry_cost = sum(
                (trade.notional + trade.fees.total for trade in entry_trades),
                Decimal("0"),
            )
            result_payload["positioning"] = {
                "sizing_mode": "max_affordable",
                "target_allocation_ratio": float(allocation_ratio),
                "entry_quantity": sum(trade.quantity for trade in entry_trades),
                "entry_cost": float(entry_cost),
                "initial_cash_utilization": float(entry_cost / request.initial_cash),
                "lot_size": policy.buy_lot_size,
            }
        result_payload["universe"] = universe_payload
        result_payload["aligned_start_ts"] = aligned_start_ts
        result_payload["benchmark"] = _benchmark_curve(
            result_payload.get("equity", []), benchmark_bars
        )
        result_payload["metrics"] = _extended_metrics(result_payload)
        record = _store(config).save(
            kind="backtest",
            name=request.strategy,
            result_hash=result.result_hash,
            data_fingerprint=combined_fingerprint,
            config={
                key: str(value) if isinstance(value, Decimal) else value
                for key, value in request.model_dump().items()
            },
            result=result_payload,
        )
        return {"experiment_id": record.id, **result_payload}

    return cast(
        dict[str, Any],
        jsonable_encoder(
            _safe(
                lambda: _run_recorded_workflow(
                    config,
                    experiment_name="backtest-research",
                    recorder_name=request.strategy,
                    params=request.model_dump(),
                    operation=execute,
                )
            )
        ),
    )


@app.get("/api/experiments")
def experiments(
    kind: Literal["factor", "backtest"] | None = None,
    limit: int = Query(default=40, ge=1, le=200),
) -> dict[str, Any]:
    records = list(_store(_config()).list(kind=kind))[-limit:]
    records.reverse()
    return {
        "experiments": [
            {
                "id": record.id,
                "kind": record.kind,
                "name": record.name,
                "result_hash": record.result_hash,
                "data_fingerprint": record.data_fingerprint,
                "config": record.config,
                "metrics": _experiment_metrics(record.kind, record.result),
                "created_at": record.created_at,
            }
            for record in records
        ]
    }


@app.get("/api/workflows")
def workflows(
    experiment_name: str | None = None,
    status: WorkflowStatus | None = None,
    limit: int = Query(default=40, ge=1, le=200),
) -> dict[str, Any]:
    records = _workflow_store(_config()).list(
        experiment_name=experiment_name,
        status=status,
        limit=limit,
    )
    return {"runs": [asdict(record) for record in records]}


@app.get("/api/workflows/{run_id}")
def workflow(run_id: int) -> dict[str, Any]:
    record = _workflow_store(_config()).get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="workflow run does not exist")
    return {"run": asdict(record)}


@app.post("/api/reports/build/{experiment_id}")
def build_report(experiment_id: int) -> dict[str, Any]:
    config = _config()

    def execute() -> dict[str, Any]:
        record = _store(config).get(experiment_id)
        if record is None:
            raise ValueError(f"experiment does not exist: {experiment_id}")
        output = config.research.reports_root
        if not output.is_absolute():
            output = PROJECT_ROOT / output
        artifacts = asdict(ReportBuilder().build(record, output))
        return {
            **artifacts,
            "urls": {
                kind: f"/api/reports/file/{Path(path).name}" for kind, path in artifacts.items()
            },
        }

    return cast(dict[str, Any], jsonable_encoder(_safe(execute)))


@app.post("/api/releases/export")
def export_release(request: ReleaseExportRequest) -> dict[str, Any]:
    config = _config()

    def execute() -> dict[str, Any]:
        record = _store(config).get(request.experiment_id)
        if record is None:
            raise ValueError(f"experiment does not exist: {request.experiment_id}")
        definition = _definition_store(config).get("strategy", record.name)
        destination = (
            PROJECT_ROOT
            / "reports"
            / "releases"
            / (f"{definition.name}-{record.id}-{record.result_hash[:12]}")
        )
        options = ReleaseOptions(
            source_commit=request.source_commit,
            runtime_api_version=request.runtime_api_version,
            approval_status=request.approval_status,
            allowed_markets=tuple(request.allowed_markets),
            limitations=tuple(request.limitations),
            max_position_weight=request.max_position_weight,
            max_gross_exposure=request.max_gross_exposure,
            max_daily_turnover=request.max_daily_turnover,
            max_order_notional=request.max_order_notional,
        )
        return release_receipt(export_experiment_release(destination, record, definition, options))

    return cast(dict[str, Any], jsonable_encoder(_safe(execute)))


@app.get("/api/reports/file/{name}")
def report_file(name: str) -> FileResponse:
    config = _config()
    output = config.research.reports_root
    if not output.is_absolute():
        output = PROJECT_ROOT / output
    allowed = {".html", ".json", ".csv"}
    requested = output / name
    if Path(name).name != name or requested.suffix.lower() not in allowed:
        raise HTTPException(status_code=400, detail="invalid report filename")
    if not requested.is_file() or not requested.resolve().is_relative_to(output.resolve()):
        raise HTTPException(status_code=404, detail="report file does not exist")
    return FileResponse(requested)


def _decode_json(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}


def _experiment_metrics(kind: str, result: dict[str, Any]) -> dict[str, Any]:
    if kind == "factor":
        metrics = dict(result.get("summary", {}))
        metrics["coverage_ratio"] = result.get("coverage_ratio", 0.0)
        return metrics
    return dict(result.get("metrics", {}))


def _reference_summary(connection: sqlite3.Connection, table: str, key: str) -> dict[str, Any]:
    snapshots_table = "sector_snapshots" if table == "sector_catalog" else "index_weight_snapshots"
    row = connection.execute(
        f"SELECT COUNT(*) AS catalog_rows, COUNT(DISTINCT {key}) AS datasets, "
        f"MIN(snapshot_date) AS first_snapshot, MAX(snapshot_date) AS last_snapshot "
        f"FROM {table}"
    ).fetchone()
    snapshot_rows = connection.execute(f"SELECT COUNT(*) FROM {snapshots_table}").fetchone()[0]
    return {**dict(row), "snapshot_rows": int(snapshot_rows)}


def _reference_payload(
    *,
    table_catalog: str,
    table_snapshots: str,
    key: str,
    search: str,
    selected_key: str | None,
    snapshot_date: int | None,
    limit: int,
) -> dict[str, Any]:
    config = _config()
    path = config.data.root / config.data.catalog

    def query() -> dict[str, Any]:
        with readonly_connection(path, busy_timeout_ms=config.data.busy_timeout_ms) as connection:
            available = connection.execute(
                f"SELECT MAX(snapshot_date) FROM {table_catalog}"
            ).fetchone()[0]
            effective_snapshot = snapshot_date or available
            if effective_snapshot is None:
                return {
                    "snapshot_date": None,
                    "catalogs": [],
                    "selected": selected_key,
                    "members": [],
                }
            conditions = ["snapshot_date=?"]
            params: list[object] = [effective_snapshot]
            if search.strip():
                conditions.append(f"{key} LIKE ?")
                params.append(f"%{search.strip()}%")
            catalogs = [
                dict(row)
                for row in connection.execute(
                    f"SELECT * FROM {table_catalog} WHERE "
                    + " AND ".join(conditions)
                    + f" ORDER BY {key} LIMIT ?",
                    [*params, limit],
                )
            ]
            members: list[dict[str, Any]] = []
            if selected_key:
                member_order = "weight DESC, symbol" if key == "index_code" else "symbol"
                members = [
                    dict(row)
                    for row in connection.execute(
                        f"SELECT * FROM {table_snapshots} "
                        f"WHERE snapshot_date=? AND {key}=? "
                        f"ORDER BY {member_order} LIMIT ?",
                        (effective_snapshot, selected_key, limit),
                    )
                ]
        return {
            "snapshot_date": int(effective_snapshot),
            "catalogs": catalogs,
            "selected": selected_key,
            "members": members,
        }

    return cast(dict[str, Any], jsonable_encoder(_safe(query)))


def _extended_metrics(result: dict[str, Any]) -> dict[str, float]:
    metrics = {key: float(value) for key, value in result.get("metrics", {}).items()}
    equity = result.get("equity", [])
    values = [float(point["net_value"]) for point in equity]
    returns = [
        values[index] / values[index - 1] - 1
        for index in range(1, len(values))
        if values[index - 1]
    ]
    years = max(len(values) / 252, 1 / 252)
    total_return = metrics.get("total_return", 0.0)
    metrics["annualized_return"] = (
        (1 + total_return) ** (1 / years) - 1 if total_return > -1 else -1
    )
    metrics["sharpe"] = (
        math.sqrt(252) * fmean(returns) / pstdev(returns)
        if len(returns) > 1 and pstdev(returns) > 0
        else 0.0
    )
    metrics["ending_net_value"] = values[-1] if values else 1.0
    benchmark = result.get("benchmark", [])
    benchmark_values = [float(point["net_value"]) for point in benchmark]
    benchmark_return = benchmark_values[-1] - 1 if benchmark_values else 0.0
    metrics["benchmark_total_return"] = benchmark_return
    metrics["excess_return"] = total_return - benchmark_return
    return metrics


def _benchmark_curve(equity: list[dict[str, Any]], bars: tuple[Any, ...]) -> list[dict[str, Any]]:
    closes = [(int(bar.ts), float(bar.close)) for bar in bars if bar.close is not None]
    if not closes:
        return []
    base = closes[0][1]
    if base <= 0:
        raise ValueError("benchmark ETF starts with a non-positive close")
    if equity and int(equity[0]["ts"]) < closes[0][0]:
        raise ValueError("equity starts before the first available benchmark ETF bar")
    output: list[dict[str, Any]] = []
    offset = 0
    latest = closes[0][1]
    for point in equity:
        ts = int(point["ts"])
        while offset < len(closes) and closes[offset][0] <= ts:
            latest = closes[offset][1]
            offset += 1
        output.append({"ts": ts, "net_value": latest / base})
    return output


def _total_return_benchmark_bars(
    bars: tuple[Bar, ...], actions: tuple[CorporateAction, ...]
) -> tuple[Bar, ...]:
    """Build an ETF total-return price series without changing executable prices."""
    return adjust_bars(bars, actions, mode="front_ratio")


def _corporate_action_fingerprint(actions: tuple[CorporateAction, ...]) -> str:
    payload = [asdict(action) for action in actions]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


@app.get("/{full_path:path}", include_in_schema=False)
def frontend(full_path: str) -> FileResponse:
    requested = FRONTEND_DIST / full_path
    if (
        full_path
        and requested.is_file()
        and requested.resolve().is_relative_to(FRONTEND_DIST.resolve())
    ):
        return FileResponse(requested)
    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="frontend is not built")
    return FileResponse(index)


def main() -> None:
    import uvicorn

    uvicorn.run("dyadresearch.web:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
