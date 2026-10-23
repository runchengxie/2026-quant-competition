# US execution evidence

[简体中文](us-execution-evidence.zh-CN.md)

The new US next-session adapter is an offline price-NAV diagnostic. Synthetic
contract tests pass through the existing USD cash ledger. Existing daily caches
still need execution evidence before they can support this replay. No orders are
submitted and no total-return or execution eligibility is inferred.

The adapter is separate from the five-market `next-open` experiment. Its model is
`us-next-session-price-nav.v1`. It requires USD instruments, raw signal and
execution prices, an explicit `XNYS` calendar version, time-zone-aware signal,
availability and decision times, and the first regular open strictly after the
decision. A missing first open blocks the replay rather than moving the trade.
The signal field records the source cutoff. The ledger's signal clock uses the
later availability time, before the declared decision. Daily close valuation
availability remains a modeled date-lag assumption.

Corporate-action coverage must span every input session and instrument. Known
events block this price-only model. Missing evidence also blocks. Real event-free
evidence requires an inspected, source-controlled digest in
`TRUSTED_ACTION_REVIEWS`. This registry is initially empty. Setting a JSON flag
cannot establish that a real interval is event-free. Synthetic action evidence is
accepted only with synthetic input identity and remains labeled synthetic.

Initial cash is USD 100000. Fractional sizing is explicitly modeled. Integral
sizing requires a positive integer lot size. `--fee-bps` is a finite nonnegative
commission scenario below 10000, with zero additional slippage and FX cost. The
default is 20 bps. Fees are not an estimate of any particular broker's tariff.

From the standalone `research/platform-compare` environment:

```sh
python -m platform_compare.us_next_session.run --config /absolute/us-inputs.json --output-root /absolute/new-output --fee-bps 20 --json
```

The configuration schema is `competition.us_next_session_inputs.v1`. It binds
CSV and action-evidence files by SHA-256. CSV columns are `date`, `open`, `close`.
All inputs and outputs stay outside the checkout. The CLI rechecks all bound
files after calculation and writes a diagnostic bundle plus `run.json`.

The root CLI dispatches without importing the accounting package:

```sh
python -m competition_tools.team run us-next-session --config /absolute/team.toml --experiment-config /absolute/us-inputs.json --output-root /absolute/new-output
python -m competition_tools.team execution-readiness --config /absolute/team.toml --spec /absolute/readiness-spec.json --output-root /absolute/new-readiness
```

The readiness spec contains `schema` set to
`competition.us_execution_readiness_spec.v1` and `manifests`, a list of
`path`/`sha256` records. This command inventories declared daily-manifest metadata
and missing execution evidence. It does not verify a complete price dataset,
grant trading permission or calculate performance. A raw-price declaration alone
does not establish first-regular-open, availability, listing, lot or action
coverage. Original study engines and published results remain unchanged.
