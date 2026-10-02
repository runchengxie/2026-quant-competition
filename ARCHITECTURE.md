# Competition Workspace Boundary

This repository is the control plane for the 2026 Hong Kong quantitative trading competition. It contains:

- Competition rules, open questions, and operating instructions.
- Competition-specific configuration, experiment settings, and frozen-run metadata.
- Final submission materials and their source index.

It does not duplicate the quantitative platform, data-vendor adapters, or trade-execution implementations.

## Source-of-truth locations

| Capability | Authoritative location |
|---|---|
| Raw market data, data quality, and vendor adapters | `research-workspace/market-data-platform` |
| Factors, strategy hypotheses, lifecycle, and research evidence | `research-workspace/strategy-research` |
| Strategy calculations, portfolio results, and application layer | `research-workspace/strategy-app` |
| Data orchestration, run directories, atomic publication, and execution handoff | `research-workspace/strategy-pipeline` |
| IBKR contracts, orders, risk, reconciliation, and audit | `research-workspace/quant-execution-engine` |

The competition repository reuses these capabilities through configuration, version locks, run manifests, and result indexes. Move a capability back to the corresponding `research-workspace` project only when the competition work creates a reusable capability. Do not create a second execution engine or data platform here.

## Suggested directories

```text
config/       competition-specific parameters
docs/         rules, strategy, and operating guides
experiments/  competition experiment configuration and result indexes
runs/         frozen-run metadata; large data stays in an external data lake
.env.example  committable environment-variable template
.env          private local environment variables; never commit
```
