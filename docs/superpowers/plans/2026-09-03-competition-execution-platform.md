# Competition Execution Platform Implementation Plan

> Historical implementation plan for the competition execution platform. Tasks are recorded as originally proposed; see current code and tests for completion status.

**Goal:** Implement standard target handoff, NautilusTrader/IBKR execution, event logging, recovery, and competition audit.

**Architecture:** Keep Nira and `research-workspace` as independent research sources. This repository is a local execution monorepo. A Windows runner connects to IBKR Gateway; Linux produces target files. Event logs and reconciliation establish order facts and recover state.

**Stack:** Python 3.12, NautilusTrader, IBKR TWS API, Pydantic/dataclass schemas, JSON/JSONL, pytest, and uv.

## Constraints

- Do not copy research code into the competition project; connect with `targets.json`, `lineage.json`, and stable schemas.
- The Windows runner defaults to IBKR Paper Gateway at `127.0.0.1:4002`.
- Live execution requires separate configuration, explicit safety switches, and human supervision.
- Unknown order status must be resolved through events or reconciliation.
- Never commit credentials, account details, order logs, or run artifacts.
- Use an isolated worktree and feature branch for each task; merge through a reviewed PR.

## Planned tasks

1. Freeze contracts and market model: test target validation, Japan symbols, currency, exchange, and lot-size rules; implement typed contracts and market normalization.
2. Add Nira target handoff: test reading an external target without importing Nira source paths; preserve lineage and validate output.
3. Add the NautilusTrader execution boundary: test Paper-only defaults, environment resolution, and dry-run behavior.
4. Implement the IBKR event adapter: test contract mapping and order/fill/error/disconnect event normalization; conduct a supervised Paper contract smoke test.
5. Add durable event journal and projections: test duplicate events, restart recovery, and idempotency.
6. Add broker reconciliation and competition evidence export.

Each task requires focused tests and a reviewed commit. This is a historical plan; current tests and source code are authoritative for actual implementation status.
