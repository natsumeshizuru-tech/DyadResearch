# Local simulation

The pure `build_order_plan` function is covered by
`tests/unit/test_qmt_big.py`. It verifies lot rounding, sell-before-buy order,
T+1 sell blocking, turnover limits, idempotent user order IDs and the disabled
live-trading default without importing QMT.

