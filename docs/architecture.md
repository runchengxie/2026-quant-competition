# Research and execution boundaries

[简体中文](architecture.zh-CN.md)

This repository contains a Paper-first execution boundary, competition operations material, three independent offline research packages and a bilingual project demo. External quantitative providers remain independent repositories. No submodules or provider source imports are required by the offline packages.

Competition-specific offline research and data preparation belong to this repository. Shared production datasets remain with their authoritative external owners. The team entry configures external paths and never discovers sibling source.

## Current ownership

Paths in code spans are repository-relative. The CLI implementation lives in `src/competition_tools/team`, available after installation as `python -m competition_tools.team`. Initial setup uses an external bootstrap environment, as described in the team quickstart. Operational wrappers live in `scripts/windows`. `research` contains independently packaged projects, `config` holds runtime settings and templates, and `schemas` defines artifact contracts.

| Capability | Code or contract |
| --- | --- |
| Portable setup, local readiness and synthetic demo orchestration | `src/competition_tools/team`, [team quickstart](operations/team-quickstart.md) |
| Target handoff and order/event contracts | `src/packages/contracts` |
| Market normalization, risk, audit and reconciliation | `src/packages/market_model`, `src/packages/risk`, `src/packages/audit`, `src/packages/reconciliation` |
| IBKR mapping and execution application | `src/adapters/ibkr`, `src/apps/execution_runner` |
| External Nira signal handoff | `src/strategies/nira`, versioned `targets.json` and `lineage.json` |
| Fractional-weight daily equity research | `research/equity-lab`, its own dependencies, lockfile and reports |
| Visible-queue crypto maker simulation | `research/crypto-mm`, its own dependencies, lockfile and reports |
| Optional research acceptance | `src/competition_tools/research_acceptance.py`, `experiment_acceptance.py`, `schemas/research/` |
| Reviewed public aggregates and presentation | `site/src/data/strategy-validation.json`, `site/src/i18n/`, Astro components |

Execution code does not import any research package. Root acceptance tools consume JSON/CSV and CLI outputs, not leaf Python objects. A successful research report is not an execution command. The published execution v1 target schema supports JP/US; runtime normalization also recognizes HK. That existing mismatch is unresolved. Crypto research does not expand the execution contract.

The equity package also owns the distinct six-market international diagnostic. Five-market next-open replay belongs only to the optional framework package. See [international experiments](research/international-experiments.md) for exact contracts and model limits. Neither replaces the default rotation or execution handoff.

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

`research/platform-compare` now consumes public `quant-platform` accounting APIs at fixed revision `28a32ba707ad72d1eb68cde5075663e1b3819ac7` through its own environment. Root tools retain legacy schedules and consume verified CLI aggregates. See the [accounting comparison guide](research/accounting-comparison.md). `quant-research` and `quant-deep-learning` retain research/model protocols; `quant-intel-platform` retains its reporting environment. Other providers remain integration boundaries and are not installed or connected by this change. Incompatible pandas versions and overlapping module namespaces require separate environments and versioned artifacts. No gitlink, lockfile or external repository is upgraded here.

Read-only local verification found the inspected platform default IBKR factory imports an unavailable `quant_execution_engine.broker.ibkr` module. This is separate from this repository's IBKR implementation. The inspected `quant-backtest-runtime` requires Linux and is not enabled on Windows. Passing selected provider tests does not establish an operational provider-to-broker chain.

The current acceptance slice cannot validate owner provenance or governed holdouts, so research promotion is always blocked. Complete study universes, corporate actions, causal FX, verified crypto venue/product/fees, owner model protocols, real-data accounting prerequisites and supervised Paper lifecycle validation remain follow-up work. Existing visible histories remain retrospective. The public 24-result snapshot remains historical diagnostics rather than evidence of completed integration.
