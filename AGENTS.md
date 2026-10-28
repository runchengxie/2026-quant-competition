# AGENTS.md

This repository contains the execution and operations project for the 2026 Hong Kong quantitative trading competition. Three independent offline research packages live under `research/`. Competition-specific offline research and data preparation belong here. Shared production providers and their authoritative datasets remain external.

## Project boundaries

- External research providers own their published datasets, models and research protocols. Nira signals are consumed through versioned files. Historical `research-workspace` paths are not the current ownership map; see docs/architecture.md.
- `research/crypto-mm` and `research/equity-lab` are independently packaged offline experiments with their own dependencies, tests and MIT licenses. They do not supply executable targets or connect to brokers. Do not import them into execution packages. Their report schemas are not the execution handoff contract, whose published v1 JSON schema markets remain JP/US. Runtime market normalization also recognizes HK, an existing schema/runtime discrepancy that this task does not resolve.
- `research/platform-compare` is an optional standalone accounting package. Its accounting implementation is owned locally; do not reintroduce framework dependencies. Root tools call its CLI and consume versioned artifacts, never import research or provider Python. Existing engines and public historical results remain unchanged.
- New research inputs and outputs belong under configured `DATA_ROOT/2026-quant-competition/research/<project>/`, outside source. Keep their English and zh-CN reader documentation synchronized.
- `src/competition_tools/team` provides stdlib-only initialization, locked setup, local diagnosis and synthetic demos. Default delivery must not depend on quant framework packages or sibling checkouts. Keep framework checks in optional `platform-comparison.yml`. See `docs/operations/team-quickstart.md` for profiles and result contracts.
- `src/competition_tools/datasets` owns explicit offline dataset specifications, bounded acquisition and immutable external receipts. `team data` and `team evaluate` do not promote research or authorize orders. Daily crypto diagnostics live in `research/crypto-mm/src/crypto_mm/daily`; never substitute their candles for maker event inputs. Preserve the original 24-result Pages snapshot and publish new allowlisted aggregates separately.
- This repository owns target handoff, market normalization, risk controls, NautilusTrader execution, IBKR Gateway integration, reconciliation, and competition audit evidence.
- AIVIX/Cryptoracle is used only for crypto-indicator experiments, not as a Hong Kong or Japan market-data source.
- RQData is a backup research source for A-shares, ETFs, and funds; it is not Nira's Japan equity data source.
- Never import `research-workspace` or Nira source code through local absolute paths.

## Target handoff

The research side hands off versioned `targets.json`, `lineage.json`, and schemas. The execution side must not infer strategy identity, market, or order parameters from a directory name.

Order lifecycle:

```text
targets.json → OrderIntent → BrokerCommand → OrderEvent / Fill → Projection
```

Target files are commands and handoff evidence. The broker event log is the source of truth for order events; a projection is a rebuildable current state; reconciliation handles missing events and restart recovery.

## Collaboration workflow

All code and documentation changes follow a worktree-first, PR-first workflow:

1. Check the current checkout before starting; do not work directly on `main`.
2. Create an isolated worktree and feature branch from `origin/main` under `.worktrees/`; make sure the directory is ignored by Git.
3. Keep each task focused and reviewable. Parallel work, when used, must have separate worktrees, branches, and non-overlapping core files.
4. For new features, write a failing test before the smallest implementation. Work serially when shared contracts, configuration, migrations, or execution-core dependencies are involved.
5. Run tests, static checks, security checks, and manual review inside the feature worktree. Do not bring unverified changes to `main`.
6. Commit and push the feature branch, open a pull request, and wait for review and CI before merging.
7. After merging, verify `main`, then remove the remote/local feature branch and worktree.
8. Confirm `git worktree list`, `git branch -a`, and `git status --short --branch` show no unintended residue.

Recommended branch prefixes: `feat/*`, `fix/*`, `chore/*`, and `docs/*`.

Serialize work that depends on execution core, schemas, configuration, or migrations. Read-only research, documentation, and independent tests may run in parallel.

## Execution safety

- Paper accounts and Paper Gateway are the default.
- Live trading requires separate configuration, explicit guard switches, and human supervision.
- Never commit `.env`, `.env.*`, API keys, account information, order logs, or run artifacts.
- Before an order, validate the account, contract, price, quantity, market session, and risk limits.
- Do not infer that an unknown order was rejected or filled; confirm through broker events or reconciliation.
- Tests use mocks or Paper, never real money for automated testing.

## Code organization

Keep this repository as a workflow-oriented monorepo with independently installable research packages. Map changes to acquisition, validation/normalization, signals, portfolio construction, replay, evaluation/publication or execution/reconciliation before adding a module. Use existing owners listed in `docs/architecture.md`; do not add empty layers or require sibling Quant repositories. Portfolio policy must not import replay or broker code. Preserve model-specific timing, accounting and market assumptions when sharing mechanisms. Performance diagnostics do not imply a general attribution engine.

- `research/equity-lab/src/equity_lab/portfolio`: weight construction and constraints, independent of replay accounting. Preserve the public `equity_lab.backtest.engine` imports and defaults.
- `research/equity-lab/src/equity_lab/data/preparation.py`: the existing demo's panel alignment, filling and source-quality flags. Do not apply this filling policy to strict predictive or execution-evidence inputs.
- `research/equity-lab/src/equity_lab/evaluation`: measurements of supplied signal and portfolio tables, without strategy execution, plotting or data acquisition. New internal callers use these canonical modules. Preserve the public functions re-exported by `backtest.prep` and `backtest.metrics` until a separately reviewed API migration; do not put implementation back into those compatibility modules.
- `research/crypto-mm/src/crypto_mm/data`, `signals`, and `portfolio`: daily price validation, historical trend definitions and target/calendar policies, without daily replay or maker imports. Existing `daily` APIs re-export their public helpers and consume the unchanged cash ledger.
- `src/competition_tools/check_workflow_boundaries.py`: CI import-direction guard. Check its actual rules before adding a dependency; keep independent leaf imports out of root code and reverse replay imports out of pure layers. Static checks are not a runtime security sandbox.
- `src/competition_tools/evaluation/run_record.py` and `contributions.py`: versioned private experiment bundles and file-based model price/cost explanation. New workflow artifacts are engineering evidence, not research promotion or target handoff. Preserve separate currencies, model assumptions and historical snapshots. See `docs/operations/workflow-check.md`.

- `src/packages/contracts`: targets, order intents, order events, and schemas.
- `src/packages/market_model`: markets, exchanges, currencies, lot sizes, and trading calendars.
- `src/apps/execution_runner/preflight.py` and `safety.py`: execution preflight checks and kill switch.
- `src/packages/audit`: event logs, audit records, and competition evidence.
- `src/adapters/ibkr`: IBKR Gateway contracts, market data, orders, and response mapping.
- `src/apps/execution_runner`: resident execution process on Windows.
- `src/strategies/nira`: reads external Nira signals and exports targets; it does not duplicate all Nira source.
- `src/competition_tools`: local command-line utilities; do not place research datasets or artifacts here.

Connect research and execution through stable contracts. Do not copy the entire `research-workspace` into this repository.

## Verification

- Changes to contracts, order lifecycle, or broker adapters require the relevant unit tests.
- Execution-chain changes additionally require Paper account connection, contract qualification, submission, cancellation, fills, restart recovery, and reconciliation checks.
- Completion reports must include actual command results and state clearly what has not been verified against a live broker.

## Rule and publication guidance

Use the public organizer rules dated 2026-10-13 and later official notices for publicly cited guidance. Keep restricted team rule copies, personal registration material and account authorizations outside public Git. Intraday close-out is not automatically a flat day. Position/turnover eligibility affects defense/award candidacy, not continued participation. Research involving crypto does not authorize a venue/product or expand the execution target schema. Confirm the actual account, supported broker and products separately.

## Task artifact closeout

Before closing a task, update its private retention inventory under configured DATA_ROOT/2026-quant-competition/retention/<review-date>/ following [artifact retention](docs/operations/artifact-retention.md) ([简体中文](docs/operations/artifact-retention.zh-CN.md)). Preserve inputs, versioned research, ledgers, validation and recovery evidence. Unknown contents and unresolved consumers remain retained. Rebuildable dependencies require completion and dependency/process/scheduled-task checks before any separately authorized retirement; inventory never authorizes deletion. Keep private paths and inventories outside public Git.
