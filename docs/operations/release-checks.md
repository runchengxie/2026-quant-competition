# Competition release checks

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
