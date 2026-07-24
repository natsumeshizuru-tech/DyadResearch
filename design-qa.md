# DyadResearch design QA

## Scope

- Product surface: local desktop research frontend
- Reference: option 2 dark quant terminal
- Supporting reference: option 1 factor research layout and analytical charts
- Primary viewport: 1440 × 1024
- Compact desktop viewport: 1024 × 720

## Comparison evidence

- Reference image: local design-generation artifact (not distributed)
- Final combined comparison: `reports/design-qa/strategy-comparison-iteration-2.png`
- Final implementation: `reports/design-qa/strategy-final.png`
- Compact implementation: `reports/design-qa/strategy-1024x720-final.png`
- Supporting views: `data-browser.png`, `factor-research.png`, `backtest.png`, `reports.png`

## Rubric

| Area | Result | Evidence |
| --- | --- | --- |
| Art direction | passed | Dark terminal palette, one-pixel separators, compact controls, Inter/monospace pairing, and teal research accent match option 2. |
| Composition | passed | Left project/factor tree, central editor, right configuration/results, and lower run log preserve the source hierarchy. |
| Option 1 integration | passed | Factor research uses a clear catalog/editor/configuration three-pane structure with time-series and distribution charts. |
| Core navigation | passed | Data, factor, strategy, backtest, and reports navigation was exercised in the in-app browser. |
| Core actions | passed | Factor analysis, strategy backtest, standalone backtest, and HTML report generation completed against the local API. |
| Data authenticity | passed | Visible instruments, bars, metrics, trades, hashes, coverage, and report paths come from the migrated read-only SQLite data and experiment store. |
| Layout and overflow | passed | Primary controls, run results, charts, and logs remain visible at 1440 × 1024; compact rules retain the core path at 1024 × 720. |
| Typography and contrast | passed | Secondary text contrast was increased and dense labels remain legible without weakening the terminal hierarchy. |
| Content and safety | passed | The UI is explicitly a research surface; no account, order, position, broker connection, or live-trading capability is exposed. |
| Browser diagnostics | passed | No application errors were recorded; one non-blocking ECharts disposed-instance warning occurred during hot-reload navigation. |

## Severity audit

- P0 remaining: 0
- P1 remaining: 0
- P2 remaining: 0
- P3 remaining: 1 non-blocking production bundle-size warning; deferred to code-splitting work because it does not affect correctness or the visible design.

final result: passed
