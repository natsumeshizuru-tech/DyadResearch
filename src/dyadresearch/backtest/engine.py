from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import asdict
from decimal import Decimal

from dyadresearch.backtest.broker import Broker
from dyadresearch.backtest.models import ACTIVE_ORDER_STATUSES, BacktestResult
from dyadresearch.backtest.policy import BacktestPolicy
from dyadresearch.data.models import Bar, CorporateAction
from dyadresearch.strategy.sdk import Strategy, StrategyContext


class BacktestEngine:
    def run(
        self,
        strategy: Strategy,
        *,
        bars: tuple[Bar, ...],
        data_fingerprint: str,
        policy: BacktestPolicy,
        corporate_actions: tuple[CorporateAction, ...] = (),
    ) -> BacktestResult:
        if not bars:
            raise ValueError("backtest requires at least one bar")
        broker = Broker(policy)
        context = StrategyContext(broker)
        strategy.initialize(context)
        strategy.on_start(context)
        timeline: dict[int, list[Bar]] = defaultdict(list)
        for bar in bars:
            timeline[bar.ts].append(bar)
        actions_by_date: dict[int, list[CorporateAction]] = defaultdict(list)
        for action in corporate_actions:
            actions_by_date[action.action_date].append(action)
        last_date: int | None = None
        for sequence, ts in enumerate(sorted(timeline), start=1):
            current = tuple(sorted(timeline[ts], key=lambda item: item.symbol))
            broker.begin_slice(ts, sequence, current)
            current_date = current[0].trade_date
            if current_date != last_date:
                broker.apply_actions(tuple(actions_by_date.get(current_date, ())))
                last_date = current_date
            strategy.before_bars(context)
            for trade in broker.execute_pending():
                strategy.on_trade(context, trade)
            broker.mark_to_market()
            context._publish(current)
            strategy.on_bars(context, current)
        strategy.on_stop(context)
        for order in broker.orders:
            if order.status in ACTIVE_ORDER_STATUSES:
                broker.cancel(order.order_id, reason="end_of_backtest")
        broker.assert_invariants()
        payload = _result_payload(broker, data_fingerprint, policy, len(timeline))
        result_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        return BacktestResult(
            run_id=f"run-{result_hash[:16]}",
            result_hash=result_hash,
            data_fingerprint=data_fingerprint,
            policy=asdict(policy),
            bars_processed=len(timeline),
            orders=tuple(broker.orders),
            trades=tuple(broker.trades),
            equity=tuple(broker.equity),
            final_positions={
                symbol: position.quantity
                for symbol, position in broker.positions.items()
                if position.quantity
            },
            metrics=_metrics(broker),
            event_log=tuple(broker.event_log),
        )


def _result_payload(
    broker: Broker, data_fingerprint: str, policy: BacktestPolicy, bars_processed: int
) -> dict[str, object]:
    return {
        "data_fingerprint": data_fingerprint,
        "policy": asdict(policy),
        "bars_processed": bars_processed,
        "orders": [asdict(item) for item in broker.orders],
        "trades": [asdict(item) for item in broker.trades],
        "equity": [asdict(item) for item in broker.equity],
        "events": broker.event_log,
    }


def _metrics(broker: Broker) -> dict[str, float]:
    if not broker.equity:
        return {}
    final_assets = broker.equity[-1].total_assets
    max_drawdown = min((point.drawdown for point in broker.equity), default=Decimal("0"))
    turnover = sum((trade.notional for trade in broker.trades), Decimal("0"))
    return {
        "total_return": float(final_assets / broker.policy.initial_cash - Decimal("1")),
        "max_drawdown": float(max_drawdown),
        "turnover_notional": float(turnover),
        "trade_count": float(len(broker.trades)),
    }
