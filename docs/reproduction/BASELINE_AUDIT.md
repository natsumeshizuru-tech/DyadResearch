# DyadResearch paper reproduction baseline audit

Audit date: 2026-07-25  
Repository: `F:\DyadTetrade\DyadResearch`  
Initial branch: `agent/readme-miniqmt` at `6b7bdf3`  
Initial worktree: clean (`git status --short` returned no entries)

## Scope and repository boundary

The active Git repository is `F:\DyadTetrade\DyadResearch`, not its parent
`F:\DyadTetrade`. The repository already has a GitHub remote:
`https://github.com/natsumeshizuru-tech/DyadResearch.git`.

The paper reproduction must extend this repository. It must not introduce a
second market-data store, experiment store, broker, or research web
application.

## Existing reusable capabilities

| Capability | Existing implementation | Reuse decision |
| --- | --- | --- |
| Packaging and CLI | `pyproject.toml`, `dyadresearch.cli` | Extend the existing `reproduce` command group |
| Factor definition | `factors.spec.FactorSpec`, `factors.registry` | Adapt paper metadata to `FactorSpec`; keep the paper formula ledger as richer metadata |
| Factor evaluation | `factors.evaluator.FactorEvaluator` | Reuse for compatible factors; add a restricted paper-expression layer |
| Read-only market data | `data.sqlite.readonly_connection`, `data.query.MarketDataReader` | Reuse; source SQLite remains read-only |
| PIT financial data | `data.financial` and documented announcement-time policy | Reuse and add reproduction-specific field checks |
| Data fingerprinting | `data.manifest.query_fingerprint` | Reuse in experiment provenance |
| Experiment persistence | `experiments.store.ExperimentStore` | Reuse; no second experiment database |
| Backtest engine | `backtest.engine.BacktestEngine` | Reuse for A-share transfer experiments |
| A-share broker constraints | `backtest.broker.Broker`, policies and fee models | Reuse for T+1, lots, suspensions, price limits and fees |
| Reporting | `reporting.builder.ReportBuilder` plus reproduction HTML/JSON/CSV export | Extend with paper-specific acceptance reports |
| Web UI | React/Vite application in `frontend/` | Keep the research-only boundary; expose research results, not live order entry |

## Runtime and local start

- Required Python: `>=3.12`; audited runtime: Python 3.12.10.
- SQLite runtime: 3.49.1.
- Editable development environment: `.venv`.
- Backend: `.venv\Scripts\dyadresearch-web`.
- Frontend: `pnpm run dev` from `frontend/`.
- Production frontend build: `pnpm run build`.

## Baseline verification

Executed before paper-reproduction code changes:

| Check | Result |
| --- | --- |
| `python -m pytest` | 106 passed in 126.18 seconds |
| `python -m ruff check src tests` | passed |
| `python -m ruff format --check src tests` | 86 files already formatted |
| `python -m mypy -p dyadresearch` | passed, 56 source files checked |
| `pnpm run test` | 1 file / 1 test passed |
| `pnpm run lint` | passed |
| `pnpm run build` | passed; Vite built 5,228 modules, with a pre-existing large-chunk warning |
| `dyadresearch doctor` | all environment and read-only checks passed |

## Data capability baseline

`dyadresearch doctor` reported:

- Daily bars: 2010-01-04 through 2026-07-24, lifecycle-aware and complete
  for the catalogued stock, ETF and index universe.
- Point-in-time financial tables: 2010-01-01 through 2026-07-17.
- Delisted universe: 285 official Shanghai/Shenzhen lifecycles catalogued;
  282 have bars and 3 have audited empty upstream results.
- Minute bars: only approximately 2025-07 onward; unsuitable for historical
  intraday execution reconstruction.
- Industry/sector membership: only a 2026-07-17 snapshot.
- Index weights: only a 2026-07-17 snapshot.

The last two gaps prevent an honest strict reconstruction of historical
industry neutralization and CSI 500 benchmark-relative constraints for
2010-2017. A current snapshot must not be backfilled into history.

## Source-paper inspection

The two source PDFs were read from the user-supplied paths and were not copied
into the repository.

- Kakushadze (2015), 22 pages. Appendix A begins on PDF page 8 and provides
  101 formula expressions, operator definitions and input definitions.
- Guotai Junan (2017), 32 pages. The 191-factor table begins on PDF page 11.
  Visual inspection confirms line wrapping and apparent typographical/OCR
  ambiguities (for example inconsistent separators, names and parentheses).

The PDFs are reference inputs only. They must remain untracked and unpublished.

## Integration constraints

1. Paper formula records may be more detailed than `FactorSpec`, but executable
   records must adapt to the existing registry rather than bypass it.
2. Reproduction runs must persist through `ExperimentStore` and include data,
   universe, formula-manifest and result fingerprints.
3. A-share portfolio tests must route through the existing backtest semantics.
4. Big-QMT delivery is an offline target-weight adapter. It must default to
   dry-run and must not add live trading controls to the DyadResearch web UI.
5. No source PDF, local SQLite file, account identifier, credential or QMT
   installation path may be committed.

## Branch decision

This is a substantial change. Development will use
`feat/paper-reproductions`; force-push is prohibited.

