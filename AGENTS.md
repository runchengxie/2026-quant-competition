# AGENTS.md

This repository contains the execution and operations project for the 2026 Hong Kong quantitative trading competition. Research, backtesting, and raw data acquisition are maintained elsewhere and should not be duplicated here.

## Project boundaries

- `research-workspace` and Nira own research, backtests, factors, and signals.
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

- `packages/contracts`: targets, order intents, order events, and schemas.
- `packages/market_model`: markets, exchanges, currencies, lot sizes, and trading calendars.
- `packages/risk`: pre-trade checks and kill switch.
- `packages/audit`: event logs, audit records, and competition evidence.
- `adapters/ibkr`: IBKR Gateway contracts, market data, orders, and response mapping.
- `apps/execution_runner`: resident execution process on Windows.
- `strategies/nira`: reads external Nira signals and exports targets; it does not duplicate all Nira source.

Connect research and execution through stable contracts. Do not copy the entire `research-workspace` into this repository.

## Verification

- Changes to contracts, order lifecycle, or broker adapters require the relevant unit tests.
- Execution-chain changes additionally require Paper account connection, contract qualification, submission, cancellation, fills, restart recovery, and reconciliation checks.
- Completion reports must include actual command results and state clearly what has not been verified against a live broker.
