# Paper reproduction data contract

## Availability time

An observation is usable only when its `available_at` time is no later than the
signal cutoff. Financial values use their announcement availability rather
than the reporting-period end. Industry, ST status, index membership and index
weights require historical snapshots; a current snapshot is not historical
evidence.

A signal computed after day t's close is executed no earlier than day t+1 open
unless a separately labelled delay-0 close-auction approximation is used.

## Required daily fields

| Field | Meaning and contract |
| --- | --- |
| `open`, `high`, `low`, `close` | Unadjusted executable prices plus separately identified adjusted research series |
| `pre_close` | Previous unadjusted close used for price-limit checks |
| `volume` | Shares or lots, with unit metadata |
| `amount` | Currency turnover, with unit metadata |
| `adj_factor` | Corporate-action adjustment factor; never applied to execution cash flows |
| `suspended` | PIT trading-state flag |
| `limit_up`, `limit_down` | PIT executable bounds or an audited derivation |
| `listed_at`, `delisted_at` | Security lifecycle |
| `is_st` | Historical PIT special-treatment state |
| `total_market_cap`, `float_market_cap`, `float_shares` | PIT capitalization inputs |
| `industry` | Historical PIT industry code and taxonomy/version |
| benchmark close/membership/weight | Historical CSI 300/500 observations with effective dates |

Daily VWAP is `amount / share_volume` after applying the declared source-unit
conversion. `adv{d}` in WorldQuant formulas is the d-day mean of daily dollar
turnover (`amount`), not mean share volume.

## Style-model dependencies

The strict GTJA protocol requires:

- Beta: 250-day weighted regression, 60-day half-life.
- RSTR momentum: 500-day history, skip the most recent 21 days, 120-day
  half-life.
- LNCAP size.
- Earnings yield: EPIBS, ETOP and CETOP.
- Volatility: DASTD, CMRA and HSIGMA.
- Growth: SGRO, EGRO, EGIB and EGIB_S.
- Value: BTOP.
- Leverage: MLEV, DTOA and BLEV.
- Liquidity: STOM, STOQ and STOA.

If EPIBS, EGIB, EGIB_S or another required input is absent,
`paper_strict` is blocked. `transparent_reconstruction` may use a named reduced
model, but its missing fields and cross-sectional coverage must be recorded.

## Required guards

1. Reject a forward return or future snapshot used as a factor input.
2. Reject financial rows before their announcement availability.
3. Reject current industry/index snapshots for historical strict protocols.
4. Record data path fingerprints, date range, row count and universe
   fingerprint without publishing the underlying licensed data.
5. Keep adjusted signal prices separate from unadjusted execution prices.

