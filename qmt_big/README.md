# Big QMT ContextInfo adapter

This adapter consumes next-session target weights exported by DyadResearch. It
does not calculate the 292 paper factors inside QMT.

Workflow:

```text
DyadResearch after-close research
  -> target-weight CSV
  -> Big QMT validation and order plan
  -> dry-run or explicitly enabled NORMAL/TWAP/VWAP execution
  -> execution plan/report CSV
```

Safety defaults:

- `ENABLE_LIVE_TRADING = False`.
- No account identifier is shipped.
- `QUICK_TRADE = 0`; value 2 is rejected.
- The target date, SHA-256 signal hash, weight sum, whitelist, holding count,
  single-name weight, turnover and order notional are validated.
- The planner sells before buying, respects available (T+1) quantities and
  rounds buys to 100-share lots.
- `strategyName` and a deterministic `userOrderId` make daily submissions
  auditable and idempotent.

Copy `config_example.py` to `config_local.py` inside the Big QMT strategy
directory. Keep dry-run enabled until target CSV validation and the generated
`execution_plan.csv` have been reviewed. The exact signatures supported by the
broker's installed Big QMT build must be checked before enabling live trading.

Required target columns:

```text
trade_date,stock_code,target_weight,reference_price,experiment_id,signal_hash
```

The repository never enables live trading and never reads a real account during
tests.

