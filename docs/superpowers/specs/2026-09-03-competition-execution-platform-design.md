# Competition Execution Platform Design

## Goal

Build a lightweight, auditable execution platform for international markets. Linux/Nira produces target files; a NautilusTrader runtime on Windows connects through IBKR Gateway to a Paper account or a separately approved live account.

## Boundaries

The project does not copy `research-workspace`, Nira, or their data assets. Research emits versioned `targets.json`, `lineage.json`, and necessary signal metadata. This repository consumes those artifacts and handles pre-trade validation, order lifecycle, broker facts, recovery, and competition reporting.

## Components

```text
Nira / research-workspace
        │ targets.json + lineage.json
        ▼
contracts + market_model + risk
        ▼
NautilusTrader execution runner
        ▼
IBKR adapter → Windows IB Gateway → IBKR account
        ├── OrderEvent / Fill journal
        ├── Rebuildable order projection
        └── Reconciliation and audit evidence
```

### Contracts

Target files describe the desired portfolio without embedding broker SDK objects. `OrderIntent` represents one risk-approved order intent. `OrderEvent` and `Fill` use stable JSON schemas, UTC timestamps, and decimal quantity/price semantics.

### Market model

The market model resolves normalized symbols to exchange contracts and maintains exchange, currency, lot size, trading sessions, fees, and FX rules. Japan symbols such as `1321.T` and `7203.T` must not be handled using U.S. `.US` rules.

### Execution runner

The Windows runner maintains a Gateway connection, consumes target commands, and listens for order status, fills, errors, connection changes, and account events. A successful submission response means only that Gateway accepted the request; final status comes from events or reconciliation.

### State and recovery

The append-only event log is the factual record. Current orders, positions, and run summaries are projections that can be rebuilt from events. On startup, load local events and reconcile with Gateway. Handle disconnections, duplicate events, and unknown submission results idempotently.

### Execution policies

The first stage supports safe single-order limit/market orders and cancellation. TWAP, VWAP, POV, and other algorithms belong in a separate execution-policy layer, not the IBKR adapter. They receive a common order intent and produce child-order plans.

## Repository and environment

Use a local monorepo for competition execution, contracts, market model, risk, and audit. Keep the research repository and Nira independent; share stable code only through small versioned packages or file contracts.

- Paper Gateway defaults to Windows `127.0.0.1:4002`.
- Do not put live-account configuration in project `.env` files.
- Inject RQData and Cryptoracle credentials only through the local environment; never write them to event logs.
- Linux does not hold the IBKR API connection; the Windows runner is the only Gateway client.

## Acceptance criteria

1. A Paper account can qualify U.S. stocks, Japanese stocks, and Japanese ETFs.
2. Events capture submission, acceptance, partial fills, fills, cancellation, rejection, errors, and disconnections.
3. Restart does not duplicate orders and reconciliation restores unknown states.
4. Nira can export `targets.json` that passes schema, market, and risk validation.
5. Order/fill evidence can be exported for competition review without revealing credentials.
6. Paper and live configurations remain clearly separated in code and at runtime.
