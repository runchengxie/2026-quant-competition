# Manual observation registry

[简体中文](observation-registry.zh-CN.md)

A frozen protocol records a decision. It does not mean data collection or a
forward performance record has started. Without admissible new data, its status
is `awaiting_new_data` and `first_eligible_observation_at` is null.

The six fixed candidates are US `mom20_monthly`,
`mom20_monthly_buffer20`, `ew_monthly`, and crypto
`trend200_vol40_strict`, `ew_trend_gross_matched`, `ew_legacy`. US fees are
20/40 bps and crypto fees are 0/10/25 bps. Each candidate/fee account begins at
NAV 1 and is replayed continuously from the same initial state. Historical study
folds are independently cash-started and cannot be joined into this account.

`competition.observation_protocol.v1` binds the candidate list, fees, actual UTC
freeze, known observation cutoff, exactly 252 unscored warmup rows per market,
universe, source hashes and retained source, initial NAV, valuation convention,
strict zero-volatility rule, import budgets and stop conditions. Revisions create
a new registry. Existing protocol and accepted receipts are never overwritten.

All configuration, warmup JSON, manifests, source snapshots and receipts belong
outside the checkout. Use the configured external team environment:

`/absolute/...` paths are placeholders. Windows needs drive-qualified absolute
paths resolved from project configuration. Replay environments must use the
retained or byte-matching scientific source; a changed editable checkout blocks
the frozen protocol's producer hash check.

```sh
python -m competition_tools.team observe freeze --config /absolute/team.toml --spec /absolute/protocol-template.json --registry-root /absolute/new-registry
python -m competition_tools.team observe append --config /absolute/team.toml --manifest /absolute/import.json --registry-root /absolute/existing-registry
python -m competition_tools.team observe status --config /absolute/team.toml --registry-root /absolute/existing-registry
```

The CLI records the current UTC time. It has no option to backdate a freeze or
import. The Python API accepts an explicit clock for deterministic tests.

Each `competition.observation_import.v1` contains one market's complete immutable
252-row warmup followed by its accumulated observation rows, per-row availability
times, price basis and quote currency. US uses the existing split-adjusted USD
price proxy. Crypto uses raw USDT prices. USD and USDT are not interchangeable.
The import supplies the full prefix so the installed independent leaf can replay
the original account. The root independently checks arithmetic and compares every
previous net and gross period before accepting an extension.

Availability must be after both freeze and known cutoff, after the completed
daily bar and no later than the import clock. Every expected session is required.
Synthetic imports use an explicitly synthetic daily grid. Real US imports use
`XNYS`; crypto uses consecutive UTC dates. Unknown availability blocks an import.
Real availability evidence requires a reviewed source-controlled digest in
`TRUSTED_AVAILABILITY_EVIDENCE`, initially empty. Caller flags cannot grant it.
Synthetic evidence remains labeled `synthetic_valuation_only`.

`competition.observation_availability_review.v1` binds the exact protocol, market
and normalized import hash, with a verified decision and aware review time. Hash
the complete import after normalizing availability times to UTC ISO-8601 and
omitting only `availability_evidence`. A review for another import cannot be
reused. Accepted receipts recheck the original evidence bytes on inspection.
Real US availability may follow the exchange close on the same UTC date; crypto
and the synthetic daily grid require the completed UTC day.

Do not import old cached tails as prospective data. A stale warmup with missing
sessions before the first proposed observation blocks the import. When approved
fresh data supplies a complete warmup, create a new protocol rather than editing
the original one. A price-only observation is not execution evidence.

Each import can add at most 512 dates and consumes one 3600-second clock including
validation, calculation and receipt preparation. Prior dates remain in the same
account and do not count as new dates. Unknown or exhausted spend blocks repeating
the same price calculation, including attempts that only change availability
metadata. There is no automatic retry or budget reset.

Exact duplicates and offset-equivalent availability timestamps are idempotent.
Conflicting prices, missing or out-of-order sessions, changed source bytes,
changed prior account rows and concurrent appends block acceptance. Failed
attempts leave no accepted receipt. Receipt hashes bind retained request/result
files, original import bytes and the previous receipt. This detects local changes;
it is not an external timestamp or proof that nobody previously inspected data.

These commands do not download, schedule, log in, connect to a broker or submit
orders. Data acquisition, scheduling and execution require separate authorization.
