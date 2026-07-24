from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from dyadresearch.backtest.adapters import QmtStrategyAdapter, QmtStrategyProtocol
from dyadresearch.backtest.engine import BacktestEngine
from dyadresearch.backtest.policy import get_policy
from dyadresearch.config import ResearchConfig, load_config
from dyadresearch.data.capabilities import capability_matrix
from dyadresearch.data.catalog import CatalogReader
from dyadresearch.data.periods import query_period_bars
from dyadresearch.data.query import MarketDataReader
from dyadresearch.demo import generate_sample_data
from dyadresearch.doctor import run_doctor
from dyadresearch.errors import DyadResearchError
from dyadresearch.experiments.compare import compare_experiments
from dyadresearch.experiments.store import ExperimentRecord, ExperimentStore
from dyadresearch.factors.evaluator import FactorEvaluator
from dyadresearch.factors.examples import register_examples
from dyadresearch.factors.registry import factor_registry
from dyadresearch.reporting.builder import ReportBuilder
from dyadresearch.reproductions import run_reproduction
from dyadresearch.reproductions.gtja_short_cycle import (
    register_factor_specs as register_gtja_factors,
)
from dyadresearch.reproductions.paper_runner import (
    audit_paper,
    compare_paper_experiments,
    run_paper_protocol,
)
from dyadresearch.reproductions.site import export_site
from dyadresearch.reproductions.worldquant101 import (
    register_factor_specs as register_worldquant_factors,
)
from dyadresearch.strategy.examples import (
    BuyAndHoldStrategy,
    MovingAverageCrossStrategy,
    QmtBuyAndHoldStrategy,
)
from dyadresearch.strategy.sdk import Strategy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dyadresearch")
    parser.add_argument("--config", default="config/research.yaml")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    demo = commands.add_parser("demo")
    demo_children = demo.add_subparsers(dest="demo_command", required=True)
    generate = demo_children.add_parser("generate-data")
    generate.add_argument("--root", type=Path)
    generate.add_argument("--overwrite", action="store_true")
    _data_parser(commands)
    _factor_parser(commands)
    _backtest_parser(commands)
    _experiment_parser(commands)
    _reproduction_parser(commands)
    _report_parser(commands)
    return parser


def _data_parser(commands: Any) -> None:
    data = commands.add_parser("data")
    children = data.add_subparsers(dest="data_command", required=True)
    children.add_parser("status")
    validate = children.add_parser("validate")
    validate.add_argument("--deep", action="store_true")
    query = children.add_parser("query")
    _query_arguments(query)
    query.add_argument("--limit", type=int, default=20)


def _factor_parser(commands: Any) -> None:
    factor = commands.add_parser("factor")
    children = factor.add_subparsers(dest="factor_command", required=True)
    children.add_parser("list")
    run = children.add_parser("run")
    run.add_argument("--name", required=True)
    _query_arguments(run)


def _backtest_parser(commands: Any) -> None:
    backtest = commands.add_parser("backtest")
    children = backtest.add_subparsers(dest="backtest_command", required=True)
    children.add_parser("list")
    run = children.add_parser("run")
    _backtest_arguments(run)
    qmt = children.add_parser("run-qmt")
    _backtest_arguments(qmt, include_strategy=False)


def _experiment_parser(commands: Any) -> None:
    experiment = commands.add_parser("experiment")
    children = experiment.add_subparsers(dest="experiment_command", required=True)
    show = children.add_parser("show")
    show.add_argument("id", type=int)
    reproduce = children.add_parser("reproduce")
    reproduce.add_argument("id", type=int)
    compare = children.add_parser("compare")
    compare.add_argument("left_id", type=int)
    compare.add_argument("right_id", type=int)


def _report_parser(commands: Any) -> None:
    report = commands.add_parser("report")
    children = report.add_subparsers(dest="report_command", required=True)
    build = children.add_parser("build")
    build.add_argument("--id", type=int, required=True)
    build.add_argument("--output")


def _reproduction_parser(commands: Any) -> None:
    reproduce = commands.add_parser("reproduce")
    children = reproduce.add_subparsers(dest="reproduce_command", required=True)
    list_command = children.add_parser("list")
    list_command.add_argument("--spec-root", type=Path, default=Path("reproductions/specs"))
    audit = children.add_parser("audit")
    audit.add_argument("paper")
    run = children.add_parser("run")
    run.add_argument("target")
    run.add_argument("--protocol")
    run.add_argument("--output", type=Path, default=Path("reproductions/generated"))
    compare = children.add_parser("compare")
    compare.add_argument("left_id", type=int)
    compare.add_argument("right_id", type=int)
    export = children.add_parser("export-site")
    export.add_argument("--output", type=Path, default=Path("site"))


def _query_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--symbols", required=True)
    parser.add_argument(
        "--period",
        choices=("1m", "5m", "15m", "30m", "1h", "1d", "1w", "1mon", "1q", "1hy", "1y"),
        default="1d",
    )
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)


def _backtest_arguments(parser: argparse.ArgumentParser, *, include_strategy: bool = True) -> None:
    if include_strategy:
        parser.add_argument(
            "--strategy", choices=("buy_and_hold", "moving_average_cross"), required=True
        )
    _query_arguments(parser)
    parser.add_argument(
        "--policy",
        choices=("strict_research", "qmt_compat", "legacy_compare"),
        default="strict_research",
    )
    parser.add_argument("--initial-cash", default="1000000")
    parser.add_argument("--quantity", type=int, default=100)
    parser.add_argument("--fast", type=int, default=5)
    parser.add_argument("--slow", type=int, default=20)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        payload = _dispatch(args, config)
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return 0 if bool(payload.get("ok", True)) else 2
    except (DyadResearchError, FileNotFoundError, KeyError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


def _dispatch(args: argparse.Namespace, config: ResearchConfig) -> dict[str, Any]:
    if args.command == "demo":
        root = args.root if args.root is not None else Path("examples") / "sample_data" / "sqlite"
        return generate_sample_data(root, overwrite=bool(args.overwrite))
    if args.command == "doctor":
        return run_doctor(config)
    if args.command == "data":
        return _data_command(args, config)
    if args.command == "factor":
        return _factor_command(args, config)
    if args.command == "backtest":
        return _backtest_command(args, config)
    if args.command == "experiment":
        return _experiment_command(args, config)
    if args.command == "reproduce":
        return _reproduction_command(args, config)
    return _report_command(args, config)


def _reproduction_command(args: argparse.Namespace, config: ResearchConfig) -> dict[str, Any]:
    if args.reproduce_command == "list":
        return {
            "specs": [str(path) for path in sorted(args.spec_root.glob("*.yaml"))],
            "papers": {
                "worldquant101": [
                    "formula-validation",
                    "original-market",
                    "ashare-transfer",
                ],
                "gtja-short-cycle": [
                    "paper-strict",
                    "transparent-reconstruction",
                    "ashare-executable",
                ],
            },
        }
    if args.reproduce_command == "audit":
        return {"ok": True, **audit_paper(args.paper)}
    if args.reproduce_command == "compare":
        return compare_paper_experiments(config, args.left_id, args.right_id)
    if args.reproduce_command == "export-site":
        return export_site(args.output)
    if args.protocol:
        return run_paper_protocol(
            config,
            args.target,
            args.protocol,
            output_root=args.output,
        )
    spec = Path(args.target)
    if not spec.is_file():
        raise ValueError("paper runs require --protocol; legacy runs require an existing spec path")
    return run_reproduction(config, spec, output_root=args.output)


def _data_command(args: argparse.Namespace, config: ResearchConfig) -> dict[str, Any]:
    if args.data_command == "status":
        return {
            "root": str(config.data.root),
            "capabilities": capability_matrix(config.data.root),
        }
    if args.data_command == "validate":
        return _validate(config, deep=bool(args.deep))
    result = query_period_bars(
        MarketDataReader(config.data),
        _symbols(args.symbols),
        period=args.period,
        start=args.start,
        end=args.end,
    )
    return {
        "rows": len(result.bars),
        "paths": result.paths,
        "warnings": [asdict(item) for item in result.warnings],
        "fingerprint": result.fingerprint,
        "data": [_jsonable(bar.to_dict()) for bar in result.bars[: args.limit]],
    }


def _factor_command(args: argparse.Namespace, config: ResearchConfig) -> dict[str, Any]:
    register_examples()
    if args.factor_command == "run" and args.name.startswith("wq101_"):
        register_worldquant_factors()
    if args.factor_command == "run" and args.name.startswith("gtja_"):
        register_gtja_factors()
    if args.factor_command == "list":
        return {
            "factors": [
                {
                    "name": spec.name,
                    "version": spec.version,
                    "lookback": spec.lookback,
                    "frequency": spec.frequency,
                    "description": spec.description,
                }
                for spec in factor_registry.list()
            ]
        }
    record = _run_factor(
        config,
        name=args.name,
        symbols=_symbols(args.symbols),
        period=args.period,
        start=args.start,
        end=args.end,
    )
    return _record_payload(record)


def _run_factor(
    config: ResearchConfig,
    *,
    name: str,
    symbols: list[str],
    period: str,
    start: int,
    end: int,
) -> ExperimentRecord:
    register_examples()
    spec = factor_registry.get(name)
    if period != spec.frequency:
        raise ValueError(f"factor {name} requires period {spec.frequency}")
    query = query_period_bars(
        MarketDataReader(config.data), symbols, period=period, start=start, end=end
    )
    result = FactorEvaluator().evaluate(spec, query.bars, data_fingerprint=query.fingerprint)
    result_payload = asdict(result)
    return _store(config).save(
        kind="factor",
        name=name,
        result_hash=result.result_hash,
        data_fingerprint=query.fingerprint,
        config={
            "name": name,
            "symbols": symbols,
            "period": period,
            "start": start,
            "end": end,
        },
        result=result_payload,
    )


def _backtest_command(args: argparse.Namespace, config: ResearchConfig) -> dict[str, Any]:
    if args.backtest_command == "list":
        return {
            "strategies": ["buy_and_hold", "moving_average_cross"],
            "qmt_strategies": ["qmt_buy_and_hold"],
            "policies": ["strict_research", "qmt_compat", "legacy_compare"],
        }
    qmt = args.backtest_command == "run-qmt"
    record = _run_backtest(
        config,
        strategy="qmt_buy_and_hold" if qmt else args.strategy,
        qmt=qmt,
        symbols=_symbols(args.symbols),
        period=args.period,
        start=args.start,
        end=args.end,
        policy_name=args.policy,
        initial_cash=Decimal(args.initial_cash),
        quantity=args.quantity,
        fast=args.fast,
        slow=args.slow,
    )
    return _record_payload(record)


def _run_backtest(
    config: ResearchConfig,
    *,
    strategy: str,
    qmt: bool,
    symbols: list[str],
    period: str,
    start: int,
    end: int,
    policy_name: str,
    initial_cash: Decimal,
    quantity: int,
    fast: int,
    slow: int,
) -> ExperimentRecord:
    query = query_period_bars(
        MarketDataReader(config.data), symbols, period=period, start=start, end=end
    )
    primary = symbols[0]
    selected: Strategy
    if qmt:
        raw_qmt = QmtBuyAndHoldStrategy(primary, quantity)
        selected = QmtStrategyAdapter(cast(QmtStrategyProtocol, raw_qmt), symbols)
    elif strategy == "buy_and_hold":
        selected = BuyAndHoldStrategy(primary, quantity)
    elif strategy == "moving_average_cross":
        selected = MovingAverageCrossStrategy(primary, fast=fast, slow=slow, quantity=quantity)
    else:
        raise ValueError(f"unknown strategy: {strategy}")
    policy = get_policy(policy_name, initial_cash=initial_cash)
    actions = CatalogReader(config.data).corporate_actions(symbols, start, end)
    result = BacktestEngine().run(
        selected,
        bars=query.bars,
        data_fingerprint=query.fingerprint,
        policy=policy,
        corporate_actions=actions,
    )
    settings = {
        "strategy": strategy,
        "qmt": qmt,
        "symbols": symbols,
        "period": period,
        "start": start,
        "end": end,
        "policy": policy_name,
        "initial_cash": str(initial_cash),
        "quantity": quantity,
        "fast": fast,
        "slow": slow,
    }
    return _store(config).save(
        kind="backtest",
        name=strategy,
        result_hash=result.result_hash,
        data_fingerprint=query.fingerprint,
        config=settings,
        result=result.to_dict(),
    )


def _experiment_command(args: argparse.Namespace, config: ResearchConfig) -> dict[str, Any]:
    store = _store(config)
    if args.experiment_command == "show":
        return _record_payload(_required_record(store, args.id))
    if args.experiment_command == "compare":
        left = _required_record(store, args.left_id)
        right = _required_record(store, args.right_id)
        return compare_experiments(left, right)
    original = _required_record(store, args.id)
    reproduced = _reproduce(config, original)
    return {
        "original_id": original.id,
        "reproduced_id": reproduced.id,
        "same_result_hash": original.result_hash == reproduced.result_hash,
        "same_data_fingerprint": original.data_fingerprint == reproduced.data_fingerprint,
        "result_hash": reproduced.result_hash,
    }


def _reproduce(config: ResearchConfig, record: ExperimentRecord) -> ExperimentRecord:
    values = record.config
    if record.kind == "factor":
        return _run_factor(
            config,
            name=str(values["name"]),
            symbols=list(values["symbols"]),
            period=str(values["period"]),
            start=int(values["start"]),
            end=int(values["end"]),
        )
    if record.kind == "backtest":
        return _run_backtest(
            config,
            strategy=str(values["strategy"]),
            qmt=bool(values["qmt"]),
            symbols=list(values["symbols"]),
            period=str(values["period"]),
            start=int(values["start"]),
            end=int(values["end"]),
            policy_name=str(values["policy"]),
            initial_cash=Decimal(str(values["initial_cash"])),
            quantity=int(values["quantity"]),
            fast=int(values["fast"]),
            slow=int(values["slow"]),
        )
    raise ValueError(f"cannot reproduce experiment kind: {record.kind}")


def _report_command(args: argparse.Namespace, config: ResearchConfig) -> dict[str, Any]:
    record = _required_record(_store(config), args.id)
    output = Path(args.output) if args.output else config.research.reports_root
    return asdict(ReportBuilder().build(record, output))


def _validate(config: ResearchConfig, *, deep: bool) -> dict[str, Any]:
    from dyadresearch.data.sqlite import readonly_connection

    paths = sorted(config.data.root.glob("*.db"))
    results = []
    for path in paths:
        with readonly_connection(path, busy_timeout_ms=config.data.busy_timeout_ms) as con:
            pragma = "PRAGMA integrity_check" if deep else "PRAGMA quick_check"
            check = str(con.execute(pragma).fetchone()[0])
        results.append({"path": str(path), "integrity": check})
    return {
        "ok": bool(results) and all(item["integrity"] == "ok" for item in results),
        "databases": results,
    }


def _store(config: ResearchConfig) -> ExperimentStore:
    return ExperimentStore(config.research.database)


def _required_record(store: ExperimentStore, identifier: int) -> ExperimentRecord:
    record = store.get(identifier)
    if record is None:
        raise ValueError(f"experiment does not exist: {identifier}")
    return record


def _record_payload(record: ExperimentRecord) -> dict[str, Any]:
    return asdict(record)


def _symbols(value: str) -> list[str]:
    symbols = sorted({item.strip().upper() for item in value.split(",") if item.strip()})
    if not symbols:
        raise ValueError("at least one symbol is required")
    return symbols


def _jsonable(value: dict[str, Any]) -> dict[str, Any]:
    return {key: str(item) if isinstance(item, Decimal) else item for key, item in value.items()}


if __name__ == "__main__":
    raise SystemExit(main())
