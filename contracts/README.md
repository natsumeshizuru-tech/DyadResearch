# DyadQuant contracts

These JSON Schema Draft 2020-12 files define the only supported strategy handoff between DyadResearch and DyadTetrade.

- DyadResearch produces a self-contained, checksummed `StrategyReleaseBundle`.
- DyadTetrade validates the schema, checksums, strategy allowlist, runtime API, data capabilities, risk budget and approval state before import.
- The bundle never contains account identifiers, broker credentials, vendor data or local absolute paths.
- Public demonstrations stop at `paper_approved` or `qmt_sim_approved`. Live approval is never inferred from backtest evidence.

The two repositories keep byte-identical schema copies. Contract tests fail on drift.
