# International Target Manifest v2 Design

Date: 2026-10-02

## Goal

Define a broker-neutral, versioned target format that can describe a mixed-market portfolio of equities, ETFs, and futures while preserving the existing v1 contract and execution behavior.

## User decision

- Use an independent v2 manifest type. Keep the current v1 `TargetSet` reader and v1 execution path unchanged; v1 must reject v2 instead of guessing how to interpret it.

## Context and constraints

- The current v1 target has a single root `market`; consumers use it for account-market preflight and symbol qualification.
- The current IBKR adapter and runner do not support generic multi-market portfolios or futures. A metadata schema does not confer market-data or order permission.
- The competition research direction includes international ETFs, individual equities, and futures, but actual instrument eligibility, data, Paper permissions, and contest calculation need separate confirmation.
- The repository owns stable execution handoff contracts. Research artifacts and run manifests remain owned by the research-contracts package in `quant-platform`; this schema carries execution-target identity only.
- No live order path or automatic v2-to-v1 conversion is in scope.

## Selected architecture

Add an explicit `TargetManifestV2` type alongside `TargetSet`. It has no root-level market; each target carries its own instrument metadata. `TargetSet.from_dict` remains a v1-only reader. A caller must explicitly choose the v2 parser, and existing runner/preflight APIs continue accepting only `TargetSet` until a separately reviewed execution change supports v2.

### Root object

```json
{
  "schema_version": "2.0",
  "strategy_id": "international-candidate",
  "as_of": "2026-10-02T08:00:00Z",
  "reporting_currency": "USD",
  "targets": []
}
```

Root fields are exact and reject unknown properties. `as_of` is a timezone-aware UTC timestamp. `reporting_currency` uses the uppercase three-letter format of ISO 4217; instrument/account qualification must verify that the code is a recognized currency. Weights and quantities use decimal strings; their JSON numeric form is rejected to preserve precision.

### Common target fields

Each target contains `instrument`, `weight`, and optional `quantity`. Weights are in `[0, 1]` and sum to at most one across the manifest. Quantity, when present, is positive. A future target must include quantity as a positive integer contract count; a percentage weight alone is not an executable future position.

Duplicate instrument identities are rejected. Equity/ETF identity is `(asset_type, market, exchange_mic, symbol)`. Futures identity additionally includes `contract_month`.

### Security instrument

An equity or ETF instrument requires:

- `asset_type`: `equity` or `etf`;
- `symbol`: a non-empty provider-neutral canonical symbol;
- `market`: a non-empty uppercase market/region code;
- `exchange_mic`: a four-character uppercase alphanumeric MIC;
- `currency`: a three-character uppercase code in ISO 4217 format; instrument qualification verifies that it is a recognized currency.

Lot-size and broker contract qualification remain execution-time checks. The v2 parser does not use the v1 symbol suffix table to invent venue, currency, or lot-size metadata.

### Futures instrument

A futures instrument requires the security fields with `asset_type: "future"`, plus:

- `contract_month`: `YYYYMM` identifying the listed contract;
- `expiry_date`: ISO date later than the manifest's UTC calendar date;
- `multiplier`: positive decimal string;
- `tick_size`: positive decimal string;
- `roll_rule_id`: non-empty immutable identifier for the research series roll rule;
- `settlement_type`: `cash` or `physical`;
- `margin_model_id`: non-empty identifier for the margin assumptions used by the producer.

The manifest records a specific listed contract. `roll_rule_id` preserves lineage to the research series; it does not authorize the execution adapter to roll positions automatically. Margin amounts and current broker requirements must be obtained and checked separately before any order.

## Validation and serialization behavior

- Add `TargetManifestV2.from_dict` and `to_dict`; do not dispatch v2 through `TargetSet.from_dict`.
- Validate UTC timestamps, exact fields, finite decimal strings, non-empty identities, currency/MIC syntax, future month/date syntax, future positive multiplier/tick, integral positive future quantity, duplicate instruments, and total weight.
- Round-trip serialization preserves decimal strings and canonical field values.
- Unknown version values and unknown fields fail closed with `TargetValidationError`.
- v1 serialization and parsing behavior remain unchanged. Existing v1 golden tests must continue to pass.

## Safety and compatibility boundary

- The v2 manifest is an interchange contract only. It must not be accepted by `TargetSet`, `NiraHandoff`, preflight, `ExecutionRunner`, or the current IBKR adapter.
- No helper may down-convert v2 to v1 because doing so would discard venue, currency, contract month, multiplier, expiry, and roll identity.
- A later execution change must add account-market routing, per-contract IBKR qualification, market-data entitlement checks, margin/risk controls, futures lifecycle events, and explicit operator approval before submitting v2 orders.
- Public examples use synthetic identifiers and contain no licensed provider responses, account values, or live holdings.

## Acceptance criteria

1. A v2 mixed-market ETF/equity/futures payload parses and round-trips without float conversion.
2. Missing future metadata, invalid MIC/currency/date/month, expired contracts, fractional future quantity, duplicate instruments, over-allocation, and unknown fields are rejected.
3. The v1 reader still parses its existing fixtures and rejects `schema_version: "2.0"`.
4. Existing execution preflight and runner tests remain green; no v2 order can enter the current execution path.
5. A JSON Schema v2 file agrees with the Python contract on required fields and discriminated asset types.

## Out of scope

- Enabling multi-market execution or v2 parsing in `ExecutionRunner`.
- Choosing actual securities, futures contracts, or portfolio weights.
- Claiming data entitlements, contest eligibility, returns, or margin availability.
- Provider access, Paper order submission, automatic roll, or live trading.
- Duplicating research run-manifest/lineage contracts from `quant-platform`.
