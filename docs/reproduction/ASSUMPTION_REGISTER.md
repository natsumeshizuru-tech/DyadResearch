# Reproduction assumption and ambiguity register

| ID | Area | Observation | Required treatment |
| --- | --- | --- | --- |
| A-001 | WorldQuant data | Original realized alpha returns, proprietary US universe and historical classifications are unavailable | Do not run or fabricate `wq101_original_market`; emit a not-run artifact |
| A-002 | WorldQuant execution | Alphas 42, 48, 53 and 54 are delay-0 close-time signals | Report a strict close approximation separately from safe t+1-open execution |
| A-003 | Rank | Source formulas do not fully determine tie/NaN behavior | Daily percentile rank, average ties, NaNs excluded; document minimum sample |
| A-004 | Noninteger windows | WorldQuant window arguments can be noninteger | Floor positive windows before evaluation and retain the source argument |
| A-005 | VWAP units | Local `amount` and `volume` units can differ by source | Require a declared amount/volume conversion; never infer silently |
| A-006 | GTJA formulas | Table 6 contains visible line-wrap, punctuation, spelling and parenthesis ambiguities | Preserve source text, create explicit normalized candidates, mark assumptions |
| A-007 | GTJA Alpha143 | `SELF` is recursive | Bind `SELF` to the factor's t-1 value and test deterministically |
| A-008 | Fama-French inputs | `MKT`, `SMB` and `HML` are not native OHLCV columns | Strict mode reports unavailable dependency; never substitute zero |
| A-009 | Historical industry | Only the 2026-07-17 snapshot is available locally | Prohibit use for historical neutralization; transparent mode omits industry with a warning |
| A-010 | Historical index weights | Only the 2026-07-17 snapshot is available locally | Prohibit historical CSI 500 benchmark-relative claims |
| A-011 | Consensus fields | EPIBS, EGIB and EGIB_S are unavailable | Strict mode blocks; transparent mode uses a named reduced style model |
| A-012 | Historical intraday | Minute bars begin around 2025-07 | Historical next-open tests use daily open and cannot reconstruct intraday TWAP/VWAP |
| A-013 | Big QMT | No live account is authorized in this task | `ENABLE_LIVE_TRADING` remains false; local tests only generate plans |

