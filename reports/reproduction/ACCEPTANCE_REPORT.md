# Paper Reproduction Acceptance Report

Overall status: **PARTIAL**

This is an evidence report, not a claim of completed numerical reproduction.

## Formula coverage

| Paper | Ledger | Executable and smoke-tested | Not executable |
| --- | ---: | ---: | ---: |
| WorldQuant 101 | 101 | 15 | 86 |
| GTJA short-cycle | 191 | 28 | 163 |

## Protocols

| Experiment | Paper | Protocol | Status | Comparability |
| ---: | --- | --- | --- | --- |
| 256 | worldquant101 | wq101_formula_validation | partial | B |
| 257 | worldquant101 | wq101_original_market | not_run | A |
| 258 | worldquant101 | wq101_ashare_transfer | not_run | D |
| 259 | gtja_short_cycle | paper_strict | not_run | A |
| 260 | gtja_short_cycle | transparent_reconstruction | partial | C |
| 261 | gtja_short_cycle | ashare_executable | partial | D |

## Data and PIT

- Daily bars and PIT financial history are available locally.
- Historical industry and index-weight snapshots are not available.
- Consensus inputs EPIBS, EGIB and EGIB_S are not available.
- Strict protocols reject these gaps rather than filling them silently.

## Numerical results

- Original WorldQuant market reproduction: **NOT RUN**.
- GTJA paper-strict strategy reproduction: **NOT RUN**.
- Full A-share transfer backtest and post-2017-05 sample: **NOT RUN**.
- No paper performance values were fabricated.

## QMT and trading safety

- The existing DyadResearch backtest/broker semantics are reused.
- Big-QMT defaults to dry-run with an empty account.
- Local tests cover lot rounding, sell-first ordering, T+1 blocks, risk limits
  and deterministic user order IDs.

## Known limitations

- WorldQuant executable coverage is not 101/101.
- GTJA executable coverage is not 191/191.
- No original-market numeric reproduction is claimed.
- No full A-share backtest or post-publication OOS result is claimed.
- Big-QMT broker-version API signatures require validation in the user's terminal.
