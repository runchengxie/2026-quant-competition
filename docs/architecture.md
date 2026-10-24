# Research and execution boundaries

[简体中文](architecture.zh-CN.md)

The project stays in one repository so a teammate can install and run it without other `quant-*` checkouts. Modules follow the research and trading workflow. Research produces evidence; only a separately reviewed target handoff can enter the Paper-first execution path.

Competition-specific offline research and data preparation belong to this repository. Shared production datasets remain with their authoritative external owners. The team entry configures external paths and never discovers sibling source.

## Workflow modules in one repository

One repository contains several installable packages with separate lockfiles. Keeping code together does not require a single environment or a broker connection for offline research. The table maps responsibilities to existing code, rather than proposing a new directory for every step.

Paths beginning with `src/` or `research/` are relative to the repository root. Python-package paths use their package source roots. `equity_lab/` is under `research/equity-lab/src/`, `crypto_mm/` under `research/crypto-mm/src/`, and `platform_compare/` under `research/platform-compare/src/`.

| Responsibility | Current owner | Output and boundary |
| --- | --- | --- |
| Download data | `src/competition_tools/datasets/*_acquisition.py` and provider transports | Bounded requests and immutable external manifests. Credentials stay outside source. |
| Validate and normalize data | Dataset quality/storage modules, `equity_lab/data/preparation.py`, `crypto_mm/data/daily_prices.py`, `crypto_mm/daily/inputs.py` | Check identity, dates, units and missing observations before consumption. Retain raw inputs; each model documents its own missing-data policy. |
| Form factors and signals | `equity_lab/signals`, `equity_lab/predictive`, `crypto_mm/signals/daily_trend.py`, the separate hourly `crypto_mm/factors` | Timestamped features or scores. Future labels belong to evaluation and cannot enter an earlier decision. |
| Construct portfolios | `equity_lab/portfolio/construction.py`, `crypto_mm/portfolio/daily.py` and `rebalance.py`; equity study keeps its specific policies | Scores become weights under explicit constraints. These internal boundaries retain model differences; they are not executable orders. |
| Backtest strategies | `equity_lab/backtest`, equity study modules, `crypto_mm/daily`, the separate maker simulator | Replay weights or quotes under each model's timing and cost assumptions. Daily candles cannot supply maker queue evidence. |
| Validate and publish research | `equity_lab/evaluation/signals.py`, `equity_lab/evaluation/performance.py`, `src/competition_tools/evaluation`, acceptance tools and `site` | Leaf evaluation measures supplied tables. Root tools invoke leaf CLIs and read versioned artifacts. Pages receives reviewed, allowlisted aggregates. |
| Submit and reconcile orders | `src/apps/execution_runner`, `src/adapters/ibkr`, `src/packages/reconciliation`, `src/packages/audit` | Reviewed targets pass preflight and safety checks. Broker events and fills feed the journal and reconciliation. |
| Explain performance | `src/competition_tools/evaluation/contributions.py`, `equity_lab/evaluation/performance.py`, package reporting and international/accounting diagnostics | Price/cost reconciliation for the named models and scoped market, FX and dividend contributions. General factor or Brinson attribution is not implemented. |

Research iterates between signals, portfolio policies and backtests. Evaluation reports what happened under a model; a separate decision determines whether a strategy can advance. Execution has its own checks and state.

```text
download → validate/normalize → factors/signals → portfolio policy → backtest
                                   ↑                ↑                │
                                   └──── research iteration ─────────┘
backtest → evaluation and scoped attribution → reviewed public aggregates

separate reviewed targets.json + lineage.json
  → execution preflight/safety → broker adapter → events/fills → reconciliation
```

The extracted equity weight policies preserve the existing `BacktestConfig` and `run_equal_weight_backtest` imports, defaults and arithmetic. They retain the legacy target-weight turnover convention; extracting them does not turn it into drift-aware, self-financing accounting. The engine still owns signal lag, returns and fees. Crypto daily and maker policies retain their different models.

The equity demo prepares its market panel in `data/preparation.py`, evaluates signals in `evaluation/signals.py`, and measures portfolio results in `evaluation/performance.py`. These modules import neither replay nor plotting. Services and report writers consume their results. Existing public functions remain available from `backtest.prep` and `backtest.metrics` through explicit re-exports. Those small compatibility modules contain no calculation implementation; removing the old paths requires a separate API migration.

This extraction preserves the demo's existing assumptions. Preparation can fill missing bars and retains source-quality flags; strict predictive and execution-evidence inputs keep their own validation. The legacy IC helper averages valid daily correlations and falls back to a pooled correlation across dates when no daily group qualifies. That fallback is a descriptive demo diagnostic. It does not establish the independent daily factor evidence required by other studies. Annualization, sample conventions and missing metric values remain unchanged.

One inherited error is corrected in regime-return diagnostics. When a portfolio supplies equity without `daily_return`, grouping now uses the same equity-derived returns as the overall metrics. An explicit `daily_return` column still takes priority. This correction changes the formerly failing input path and leaves existing successful calculations unchanged.

Crypto daily validation, trend definitions and portfolio policies now have separate owners. Existing `daily` evaluators and their public helper imports remain available. Daily policies keep the legacy/strict zero-volatility distinction and buy-hold-like equal-weight study behavior. The maker simulator remains separate. A static import guard checks these directions in CI.

The [offline workflow check](operations/workflow-check.md) runs two installed synthetic producers through their actual modules and a stdlib root consumer. New experiment records bind retained source, inputs, parameters, environment metadata and outputs. Model-specific price/cost explanations reconcile the supplied artifacts. They leave existing research plans, receipts, schemas and public snapshots unchanged and do not promote research or authorize execution.

Future work should extract a shared mechanism only after two real consumers need the same semantics. Add contract and compatibility tests before changing a boundary. Keep provider differences in adapters, avoid reverse imports from portfolio policy into backtest, and keep research imports out of execution. Optional Quant-family integration requires a pinned interface and comparison evidence. There is no new runtime dependency or repository split.

## Current ownership

Repository and Python-package paths follow the roots above. The CLI implementation lives in `src/competition_tools/team`, available after installation as `python -m competition_tools.team`. Initial setup uses an external bootstrap environment, as described in the team quickstart. Operational wrappers live in `scripts/windows`. `research` contains independently packaged projects, `config` holds runtime settings and templates, and `schemas` defines artifact contracts.

| Capability | Code or contract |
| --- | --- |
| Portable setup, local readiness and synthetic demo orchestration | `src/competition_tools/team`, [team quickstart](operations/team-quickstart.md) |
| Target handoff and order/event contracts | `src/packages/contracts` |
| Market normalization, execution checks, audit and reconciliation | `src/packages/market_model`, `src/apps/execution_runner/preflight.py`, `src/apps/execution_runner/safety.py`, `src/packages/audit`, `src/packages/reconciliation` |
| IBKR mapping and execution application | `src/adapters/ibkr`, `src/apps/execution_runner` |
| External Nira signal handoff | `src/strategies/nira`, versioned `targets.json` and `lineage.json` |
| Fractional-weight daily equity research | `research/equity-lab`, its own dependencies, lockfile and reports |
| Visible-queue crypto maker simulation | `research/crypto-mm`, its own dependencies, lockfile and reports |
| Optional research acceptance | `src/competition_tools/research_acceptance.py`, `experiment_acceptance.py`, `schemas/research/` |
| Reviewed public aggregates and presentation | `site/src/data/strategy-validation.json`, `site/src/i18n/`, Astro components |

Execution code does not import any research package. Root acceptance tools consume JSON/CSV and CLI outputs, not leaf Python objects. A successful research report is not an execution command. The published execution v1 target schema supports JP/US; runtime normalization also recognizes HK. That existing mismatch is unresolved. Crypto research does not expand the execution contract.

The equity package also owns the distinct six-market international diagnostic. Five-market next-open replay belongs only to the optional accounting package. See [international experiments](research/international-experiments.md) for exact contracts and model limits. Neither replaces the default rotation or execution handoff.

## Data flow and identity

Standalone [dataset preparation](research/datasets.md) adds explicit source specifications, bounded downloads and external immutable manifests under `src/competition_tools/datasets`. Root evaluation dispatches the separately installed crypto daily CLI and reads JSON results. It does not import leaf packages or reuse daily candles as event-book inputs. The separate `strategy-expansion.v1.json` Pages projection carries new retrospective aggregates; the original 24-result snapshot stays unchanged.

```text
external dataset + explicit manifest
  → leaf input inspection → versioned input receipt
  → root exact-byte recheck + retained config/summary/observations
  → diagnostic or blocked experiment acceptance
  → separate review before any public aggregate publication
```

Raw inputs, private configuration, receipts, reports, models and figures stay outside source under configured owner data paths. Receipts bind metadata and relative file references to hashes of the original bytes. This is change detection, not independent vendor authentication or atomic snapshot isolation. Input inspection, experiment acceptance and execution handoff are separate contracts. See [the acceptance guide](research/research-acceptance.md).

Execution flow remains:

```text
targets.json + lineage.json → OrderIntent → BrokerCommand
  → OrderEvent / Fill → rebuildable Projection → reconciliation
```

The broker event log owns event truth. Paper is the default account environment, but programmatic `dry_run` defaults to false. Explicit dry-run and the required Paper preflight/lifecycle checks remain necessary. The new research tools never invoke this flow.

## External reuse and delivery limits

`research/platform-compare` now owns its USD price ledger. Both HK/US comparisons and five-market next-open experiments install/import neither `quant-platform` nor `research-contracts`. See the [accounting comparison guide](research/accounting-comparison.md) for source ancestry, licensing and historical compatibility. External datasets and Nira signals still use explicit file contracts; independent environments retain dependency isolation.

Read-only local verification found the inspected platform default IBKR factory imports an unavailable `quant_execution_engine.broker.ibkr` module. This is separate from this repository's IBKR implementation. The inspected `quant-backtest-runtime` requires Linux and is not enabled on Windows. Passing selected provider tests does not establish an operational provider-to-broker chain.

The current acceptance slice cannot validate owner provenance or governed holdouts, so research promotion is always blocked. Complete study universes, corporate actions, causal FX, verified crypto venue/product/fees, owner model protocols, real-data accounting prerequisites and supervised Paper lifecycle validation remain follow-up work. Existing visible histories remain retrospective. The public 24-result snapshot remains historical diagnostics rather than evidence of completed integration.
