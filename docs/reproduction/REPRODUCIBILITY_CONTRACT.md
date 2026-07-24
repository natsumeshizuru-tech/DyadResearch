# Reproducibility Contract

## Comparability levels

| Level | Meaning |
| --- | --- |
| A | Data, universe and methodology are highly aligned with the paper |
| B | Formula is aligned, but market, data source or universe differs |
| C | Transparent reconstruction with explicit assumptions |
| D | Tradable A-share transfer; absolute paper returns are not compared |

## Truthful status

Every formula is labelled `exact`, `normalized`, `corrected_typo`,
`assumption`, `unavailable_dependency` or `not_implemented`. A ledger count is
never presented as executable coverage.

Every protocol records its Git commit, manifest/data fingerprints, result hash,
comparability level and blockers. A missing original-market dependency produces
a `NOT_RUN.md`, not a synthetic performance number.

## Timing

Day-t close information is executed no earlier than t+1 open unless a
separately labelled delay-0 close-auction approximation is used. Financial data
is available at announcement time. Current industry or index snapshots are
never applied retrospectively in a strict protocol.

