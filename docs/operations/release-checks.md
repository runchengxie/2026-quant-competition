# Competition Release Checks

The Windows runner is Paper-first. Before a run, validate the Nira target
artifact and keep `targets.json`, `lineage.json`, the resolved non-secret
configuration, and the append-only event journal under a run ID.

Minimum checks:

1. `python -m strategies.nira.handoff validate --targets ... --lineage ...`
2. Confirm `COMPETITION_EXECUTION_ENVIRONMENT=paper` and use dry-run for the
   first validation.
3. Confirm the evidence record contains `run_id`, `strategy_id`,
   `environment`, `started_at`, and `events_file`.
4. Never put IBKR credentials, RQData licenses, AIVIX keys, or account data in
   committed files or evidence JSON.
5. A live run requires both explicit live environment guards and human
   supervision. The runner must not infer live permission from a config file.

The first Paper Gateway smoke should only connect and qualify the intended
contract. An order submission is a separate, supervised action. Unknown order
outcomes remain unknown until an IBKR event or reconnect reconciliation
resolves them.

## Current execution limitations

Before each rebalance adapter call, the runner durably records every planned client intent. These `order_submitted` entries record attempts, not broker acceptance. A journal write failure prevents submission. Client intent IDs are not yet mapped end to end to IBKR order/permId/clientId callback identities; do not treat current reconciliation tests as verified broker restart recovery. No automatic retry is safe after an unknown outcome.

The baseline TWAP planner supports whole-unit quantities only and rejects fractional units instead of increasing the requested total. Instrument-specific fractional or lot-size slicing requires an explicit quantity quantum. Handoff target and lineage destinations must resolve to different files.

The schema/runtime HK discrepancy and external producer field/lineage naming differences still require a reviewed compatibility adapter. This audit did not change target versions or initialize external repositories. Supervised Paper order, cancellation, fill, restart and reconciliation verification remains required before operational use.

## Optional Paper login helper

The [Paper Gateway helper](gateway-login.md) ([简体中文](gateway-login.zh-CN.md)) has separate installation, authentication and activation checks. Its local preflight does not establish API or historical-data readiness, and does not authorize orders.
