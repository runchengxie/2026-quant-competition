# Forward-observation readiness

At the 2026-10-23 snapshot, no real forward observation has been accepted. The
six-candidate manual protocol was frozen at 10:37:23 UTC, before the new historical
comparisons ran. Its status is `awaiting_new_data`; the first accepted availability
time is null. A frozen protocol is not a live performance record.

The new protocol fixes US `mom20_monthly`, `mom20_monthly_buffer20`, `ew_monthly`
and crypto `trend200_vol40_strict`, `ew_trend_gross_matched`, `ew_legacy`, at all
specified fees. Older US weekly `sma_cross` and HK monthly `momentum_20d` remain
separate research candidates outside this protocol. The 420-job grid supplies no
new HK experiment or execution evidence.

The [manual registry](observation-registry.md) uses one continuous modeled account
per candidate/fee from its first accepted observation. Replays retain every prior
row and cash state. Historical folds still start independently from cash and are
never joined into that account. Already inspected tails remain retrospective.

The existing warmup is stale relative to a genuinely new observation start.
Missing intervening sessions block import. After approved fresh data supplies a
complete causal warmup and reviewed availability evidence, create a new protocol;
do not rewrite the original warmup or score old cached rows as prospective data.
Real availability review is not established by caller metadata.

[Execution evidence](us-execution-evidence.md) remains a separate gate. Cached
IBKR/Databento inputs lack the required raw-open, availability, action or
lot/listing evidence. Accepting price valuations would not establish tradable
fills, capacity, account eligibility or executable target handoffs.

No collector, Gateway login, scheduler or order integration was activated. Those
operations require separate authorization. See [the new controls](strategy-controls.md)
and the [existing strategy evidence](strategies.md#formal-ablation).
