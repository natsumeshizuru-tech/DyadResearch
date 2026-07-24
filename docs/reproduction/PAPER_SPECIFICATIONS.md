# Structured paper specifications

This document records the implementation contract extracted from the two
source papers. It is not a reproduction result and does not copy the papers'
prose.

## WorldQuant 101 Formulaic Alphas

Source: Zura Kakushadze, *101 Formulaic Alphas* (2015), 22 pages.

### Publicly reproducible surface

- 101 formula expressions in Appendix A.
- Operator semantics for arithmetic, conditional expressions, cross-sectional
  ranks, rolling statistics, correlation/covariance, rolling extrema and
  arg-extrema, signed power, scaling, linear decay and industry neutralization.
- Inputs: adjusted OHLC, volume, VWAP, returns, average daily dollar volume,
  market capitalization and industry classifications at several granularities.
- Delay semantics. The paper identifies Alphas 42, 48, 53 and 54 as delay-0;
  the remaining formulas are treated as delay-1 unless a formula-specific
  review states otherwise.

### Empirical protocol disclosed by the paper

- Proprietary WorldQuant observations from 2010-01-04 through 2013-12-31.
- 1,006 return observations for 101 alphas.
- Per-alpha Sharpe, turnover, holding period, cents-per-share, return
  volatility and annualized return.
- Pairwise correlation distribution.
- Cross-sectional regressions of log return on log volatility, and on log
  volatility plus log turnover.
- A test of turnover's explanatory power for pairwise alpha correlation.

The local A-share database cannot reproduce the proprietary US universe,
industry history or realized WorldQuant alpha returns. Local results therefore
use comparability B (formula, different market/data) or D (tradable A-share
transfer), never A.

## Guotai Junan short-cycle price-volume multifactor system

Source: Guotai Junan Securities, *A multifactor stock-selection system based
on short-cycle price-volume characteristics* (2017), 32 pages.

### Formula surface

- 191 daily price-volume formulas, beginning in Table 6 on PDF page 11.
- Operator appendix covering formula-language constructs such as `SMA`, `WMA`,
  `COUNT`, `SUMIF`, `REGBETA`, `REGRESI`, `SEQUENCE`, `DTM`, `DBM`, `TR`,
  `HD`, `LD` and recursive `SELF`.
- Some formulas contain visibly ambiguous typography, spelling, punctuation,
  arguments or parentheses. The source expression must be retained separately
  from any executable candidate.
- Alpha143 uses the previous value of the factor via `SELF`; it cannot be
  evaluated as a contemporaneous circular reference.
- Fama-French inputs (`MKT`, `SMB`, `HML`) are required by relevant formulas
  and must not default silently to zero.

### Single-factor protocol

- Evaluation period disclosed in the report: 2010-01 through 2017-04.
- Daily cross-sectional residualization against industry and broad style
  factors, followed by standardization.
- Cross-sectional regression against forward 1, 2, 3, 4 and 5-day returns.
- Metrics: annualized factor return, factor-return IR, IC, RankIC, ICIR, win
  rate and coverage.
- Redundancy removal using factor-return correlations with an explicit,
  configurable threshold.

### Multifactor prediction and portfolio protocol

- Preferred prediction horizon: two days.
- Rolling factor-return lookback: 250 trading days.
- Current residual exposure times the historical factor-return mean produces
  the alpha forecast.
- Results must distinguish a static paper-style analysis, a strict walk-forward
  analysis, and post-publication results after 2017-05.
- Long-only objective: forecast return less half the configured L1 turnover
  cost.
- Fully invested, nonnegative weights.
- Benchmark: CSI 500.
- Rebalance every two trading days; next-open execution.
- Industry active-weight tolerance: approximately +/-5 percentage points.
- Style active-exposure tolerance: +/-0.1.
- Target holdings: approximately 50-60, achieved prospectively rather than
  fitted after observing the backtest.
- Baseline transaction-cost coefficient: 0.3%, with sensitivity through 1.0%.

### Local comparability limits

The local repository has daily prices and PIT financial tables but lacks
historical industry snapshots, historical CSI 500 weights and analyst-consensus
fields such as EPIBS, EGIB and EGIB_S. Therefore:

- `paper_strict` must stop or explicitly mark the missing dependencies.
- `transparent_reconstruction` may use a reduced style model only when every
  omission and substitute is recorded.
- `ashare_executable` is comparability D and cannot be compared directly with
  the paper's absolute strategy returns.

