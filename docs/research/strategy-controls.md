# Strategy controls

[简体中文](strategy-controls.zh-CN.md)

All 420 historical controls completed. They support comparisons between the fixed rules under stated costs. Real forward observations remain zero, so these results cannot establish performance on newly arriving data.

The experiments passed artifact and arithmetic
checks on 2026-10-23. The project owner confirmed authorization to display this exact result set. Pages
now publishes its 420 aggregate result rows and 224 matched comparisons, alongside
completion counts and evidence gaps. No real forward observation has started.

## What was compared

US uses the existing ten-stock fixed-current USD pool and separate SPY input,
953 sessions from 2023-01-03 through 2026-10-20. Crypto uses eight fixed-current
spot products in USDT, with 1369 complete common daily observations from
2023-01-01 through 2026-09-30. These are not historical S&P 500 or whole-market
membership datasets. No new provider request was made.

Both markets use 252 warmup rows. US has eleven complete 63-session windows at
20/40 bps. Crypto has twelve complete 90-day windows at 0/10/25 bps. The grid is
132 US plus 288 crypto jobs. Every requested job remains in the denominator.

US compares daily and monthly equal weighting and positive 20-session momentum,
with an additional monthly buffer for each signal. The buffer trades when the
sum of absolute differences between target and drifted weights, including cash,
is at least 0.20. Initial entry is allowed. Equality trades, with a 1e-12 absolute
floating point tolerance. A skipped checkpoint holds shares. An empty selection
exits at a scheduled checkpoint; it does not add a daily exit rule.

Crypto preserves the four legacy policies and adds strict trend volatility
sizing, equal weight at 60%, strict equal-weight volatility sizing and equal
weight using the strict trend policy's same lagged decision-time invested share.
Strict sizing uses 20 completed simple returns of the currently selected
basket, sample standard deviation, a 40% annual target and a leverage cap of 1.
Zero measured volatility means cash; insufficient or nonfinite inputs block the
calculation. The original equal-weight benchmark remains buy and hold. The
legacy zero-volatility fallback and post-hoc 60% label remain unchanged.

Equal invested shares do not establish equal realized risk. Inspect volatility,
drawdown and turnover alongside return. Every window starts independently at
NAV 1, with no terminal liquidation. US uses split-adjusted price accounting,
not dividend total return. USDT is not converted to USD. Do not join windows into
a continuous curve or call this untouched out-of-sample evidence.

## Evidence and publication

The historical protocol froze at 2026-10-23 10:39:17 UTC, after the six forward
candidates were fixed at 10:37:23 UTC and before calculation. Scientific source:
`eb3c146911d5708ca02682efa77795f0a077952c`. Plan SHA-256:
`c43419690ea26be3e5217d5aaa7dcf3558dd54448152d47f2a2216d0330ff87c`.

The run consumed 205.797 seconds within its one cumulative 3600-second budget.
A separate NumPy reference recomputed ten first/last-window equal-weight
trajectories from normalized source closes, including holdings, fees, cash and
all summary metrics. It checked all 224 paired identities, contexts and deltas.
This samples accounting rather than independently reimplementing every policy.
Private period artifacts, comparisons, source snapshots and reports stay external.

`competition.public_strategy_controls.v1` is the only controls input to Pages.
Its current status is `measured`: 420 requested, 420 completed, zero blocked,
420 result rows and 224 matched pairs. This is historical measurement, not an
upgrade to execution or prospective evidence. Authorization is bound to this
exact plan/result set; future releases still need their own reviewed record.
A caller boolean cannot grant publication rights.
A measured export requires a reviewed exact plan/results permission fingerprint;
the Pages gate also requires review of the exact public snapshot digest.
Existing published snapshots retain their policies, identities and scope.

## Commands and contracts

Use configured external environments. `/absolute/...` paths below are
placeholders; on Windows use drive-qualified absolute paths. Keep configuration,
inputs, retained source and output outside the checkout.

```sh
python -m competition_tools.team controls --help
python -m competition_tools.team controls --config /absolute/team.toml --spec /absolute/controls-spec.json --output-root /absolute/new-study
python -m competition_tools.check_controls_delivery --config /absolute/team.toml --output-root /absolute/new-synthetic-check
python -m competition_tools.check_controls_reference --plan /absolute/study/plan.json --results /absolute/study/run/results.json --output-root /absolute/new-reference
```

The reference command needs the existing daily-data environment, including NumPy.
`competition.strategy_controls_spec.v1` binds both manifests, their expected
hashes, the exact six/eight arms, costs and budgets. Independent leaf CLIs exchange
new versioned job, batch, result and period contracts; they do not import the root
package. Original v1/v2 study jobs, the v3 ablation specification and the old
catalog hash are unchanged.

Maximum budgets are 512 jobs, 384 per child batch and 3600 cumulative seconds,
including verification and a permitted checkpoint resume. The CLI creates a new
study; the `run_controls` API consumes an existing frozen plan for a checked
resume. Unknown spend or a changed checkpoint blocks resume. Failed attempted
jobs are not retried with a fresh budget.

See [execution evidence](us-execution-evidence.md), the
[manual observation registry](observation-registry.md) and
[forward-observation status](forward-observation-readiness.md). None of these
research commands downloads data, activates a scheduler, logs in or submits orders.

US benchmark comparisons are a separate private supplement keyed by each frozen job ID. It reports same-window SPY gross price return and fee-matched buy-and-hold net return, including the initial entry fee and no terminal sale, plus strategy net excess against each. Entry uses the last warmup close, matching the first scored return. Split-adjusted prices exclude dividend total return. The supplement does not rerun policies or modify the frozen artifacts and follows the same publication gate.
