# Research and execution boundaries

[简体中文](ARCHITECTURE.zh-CN.md)

This repository contains a Paper-first execution boundary, competition operations material, two independent offline research packages and a bilingual project demo. External quantitative providers remain independent repositories. No submodules or provider source imports are required by the offline packages.

## Current ownership

| Capability | Code or contract |
| --- | --- |
| Target handoff and order/event contracts | `src/packages/contracts` |
| Market normalization, risk, audit and reconciliation | `src/packages/market_model`, `src/packages/risk`, `src/packages/audit`, `src/packages/reconciliation` |
| IBKR mapping and execution application | `src/adapters/ibkr`, `src/apps/execution_runner` |
| External Nira signal handoff | `src/strategies/nira`, versioned `targets.json` and `lineage.json` |
| Fractional-weight daily equity research | `research/equity-lab`, its own dependencies, lockfile and reports |
| Visible-queue crypto maker simulation | `research/crypto-mm`, its own dependencies, lockfile and reports |
| Optional research acceptance | `src/competition_tools/research_acceptance.py`, `experiment_acceptance.py`, `schemas/research/` |
| Reviewed public aggregates and presentation | `site/src/data/strategy-validation.json`, `site/src/i18n/`, Astro components |

Execution code does not import either research package. Root acceptance tools consume JSON/CSV and CLI outputs, not leaf Python objects. A successful research report is not an execution command. The published execution v1 target schema supports JP/US; runtime normalization also recognizes HK. That existing mismatch is unresolved. Crypto research does not expand the execution contract.

## Data flow and identity

```text
external dataset + explicit manifest
  → leaf input inspection → versioned input receipt
  → root exact-byte recheck + retained config/summary/observations
  → diagnostic or blocked experiment acceptance
  → separate review before any public aggregate publication
```

Raw inputs, private configuration, receipts, reports, models and figures stay outside source under configured owner data paths. Receipts bind metadata and relative file references to hashes of the original bytes. This is change detection, not independent vendor authentication or atomic snapshot isolation. Input inspection, experiment acceptance and execution handoff are separate contracts. See [the acceptance guide](docs/research/research-acceptance.md).

Execution flow remains:

```text
targets.json + lineage.json → OrderIntent → BrokerCommand
  → OrderEvent / Fill → rebuildable Projection → reconciliation
```

The broker event log owns event truth. Paper is the default account environment, but programmatic `dry_run` defaults to false. Explicit dry-run and the required Paper preflight/lifecycle checks remain necessary. The new research tools never invoke this flow.

## External reuse and delivery limits

`quant-platform` is a candidate owner for accounting, simulation and research artifact contracts. `quant-research` and `quant-deep-learning` retain research/model protocols; `quant-intel-platform` retains its reporting environment. These are integration boundaries, not dependencies installed or connected by this change. Incompatible pandas versions and overlapping module namespaces require separate environments and versioned artifacts. No gitlink, lockfile or external repository is upgraded here.

Read-only local verification found the inspected platform default IBKR factory imports an unavailable `quant_execution_engine.broker.ibkr` module. This is separate from this repository's IBKR implementation. The inspected `quant-backtest-runtime` requires Linux and is not enabled on Windows. Passing selected provider tests does not establish an operational provider-to-broker chain.

The current acceptance slice cannot validate owner provenance or governed holdouts, so research promotion is always blocked. Complete study universes, corporate actions, causal FX, verified crypto venue/product/fees, owner model protocols, accounting adapters and supervised Paper lifecycle validation remain follow-up work. Existing visible histories remain retrospective. The public 24-result snapshot remains historical diagnostics rather than evidence of completed integration.
