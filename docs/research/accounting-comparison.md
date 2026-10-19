# Pinned accounting comparison

[简体中文](accounting-comparison.zh-CN.md)

The optional `research/platform-compare` package now consumes the public `quant-platform` USD price ledger at `28a32ba707ad72d1eb68cde5075663e1b3819ac7`. It compares retained legacy strategy decisions with explicit cash/share accounting. Legacy engines, default settings and the existing 24-result public snapshot remain unchanged. All new results are synthetic software diagnostics. No real-data accounting result or broker lifecycle is certified.

## What is connected

| Producer | Existing profiles | Retained schedule |
| --- | --- | --- |
| `equity-lab` | `equal_weight`, `momentum_20d` | Daily targets after the existing one-session signal lag and turnover limits |
| Root monthly engine | `pure_momentum`, `momentum_volatility` | Actual weights from the existing monthly selection call, with implicit zero targets made explicit |
| `platform-compare` | No signal generation | Maps those decisions, observations and explicit clocks into owner APIs |
| Root comparison | No provider Python imports | Runs owner verification in the optional environment, then checks allowlisted aggregate bindings |

The equity exporter uses a complete aligned session grid, refuses duplicates, nonfinite values and nonzero dividends, and does not shift already planned targets a second time. The final signal has no execution unless a next session exists. Its legacy outputs retain original floating-point summaries. Monthly observation is opt-in and does not change the result object or default behavior. US use of monthly ranking is a tested synthetic diagnostic profile, not a newly validated US trading strategy.

## Environments and commands

Use Python 3.12 and three separate external environments. Resolve paths from the machine-local workspace configuration or explicitly pass them. Do not put environments, fixtures or bundles in source. The provider's pandas version is independent of the equity environment.

```powershell
$env:UV_PROJECT_ENVIRONMENT = $rootEnvironment
uv sync --locked --extra test
$env:UV_PROJECT_ENVIRONMENT = $equityEnvironment
uv sync --project research/equity-lab --locked --group dev
$env:UV_PROJECT_ENVIRONMENT = $providerEnvironment
uv sync --project research/platform-compare --locked --group dev

& $rootPython -m competition_tools.check_accounting_comparison --output-root $newSyntheticDirectory --leaf-python $equityPython --provider-python $providerPython
```

This command creates eight cases, invokes the actual legacy producers, runs the installed pinned owner and verifies each published bundle in a second process. The output directory must be new. It writes private full comparisons plus an aggregate `summary.json`; it does not publish them to Pages. Source bytes and existing reports are not modified. The CI accounting job executes this same boundary.

For retained artifacts with an explicit clock sidecar:

```powershell
& $rootPython -m competition_tools.accounting_comparison --legacy $legacyJson --clocks $clockJson --provider-python $providerPython --request $requestJson --dataset-root $datasetRoot --bundle $ownerBundle
```

The optional package can run or independently reverify its owner bundle. See its [input contract and commands](../../research/platform-compare/README.md).

## Contracts and differences

`competition.legacy_decisions.v1` retains producer, strategy/frequency, market, synthetic state, input and legacy-config fingerprints, session-date targets and the legacy summary. It does not claim an authenticated external producer. `competition.decision_clocks.v1` binds the same input/config identities to explicit UTC research clocks and execution times. Missing clock metadata is `CLOCK_METADATA_REQUIRED`; the comparison CLI returns a sanitized blocked envelope for invalid inputs.

Each source date must precede execution; cutoff, signal, decision, order, execution and valuation times must be causal. These daily HK/US adapters require UTC clock dates matching the supplied session labels, so overnight/date-crossing policies need a separate adapter. Real session dates alone are insufficient. Clock maps and report schedules cannot contradict one another.

Owner request input/config/schedule/manifest identities, original capital and commission/slippage assumptions must match. Owner financial tables are independently reconciled by its publisher and hash-verified by its reader. Owner-produced finite Decimal exponent strings are normalized only after inventory verification; request monetary strings retain their stricter grammar. Extra unlisted sidecars are not proof of owner results.

The comparison reports both NAV values and their difference, owner cash/positions, costs, traded notional, sizing, FX assumptions and observation counts. It explicitly identifies cash/share settlement, quantity drift, lot sizing, FX, turnover/cost basis and timing differences. Equal PnL is not an acceptance criterion. The fractional-weight proxy does not drift quantities like the cash/share model. Owner sizing also scales purchases to available cash after fees. Monthly proxy summaries omit warmup cash observations while the owner retains the full synthetic valuation grid. These are distinct models, not parity failures.

## Synthetic evidence

The fixed fixture has two fictional instruments and 32 daily labels starting 2026-01-16. USD initial capital is 10,000, commission 1 bps, slippage 2 bps. HK uses synthetic HKD/USD 0.125, lots 100/200 and integral sizing; US uses USD and fractional sizing. Next-session execution marks deliberately reuse the previous synthetic close at 09:00 UTC, with valuation at 16:00 UTC. This is an artificial controlled assumption, not a real next-open price claim. Monthly smoke configurations use lookback 2 and volatility window 2; production defaults remain unchanged. The two monthly profiles choose the same targets in this small fixture.

The final eight-case rerun executed on 2026-10-19 produced the following values, rounded to four decimals. They test software behavior and must not be used as market performance, research acceptance or a promotion recommendation. Tiny residual cash in US fractional cases rounds to zero here; full precision is retained in private outputs.

| Market | Strategy | Legacy NAV | Owner NAV (USD) | Cash (USD) | Costs (USD) | Difference (USD) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| HK | equal_weight | 11879.0662 | 11541.1231 | 1241.1231 | 2.6269 | -337.9431 |
| HK | momentum_20d | 10581.5260 | 10479.1125 | 2872.8625 | 2.1375 | -102.4135 |
| HK | pure_momentum | 10812.3879 | 10798.2750 | 4248.2750 | 1.7250 | -14.1129 |
| HK | momentum_volatility | 10812.3879 | 10798.2750 | 4248.2750 | 1.7250 | -14.1129 |
| US | equal_weight | 11879.0662 | 11878.7076 | 0.0000 | 3.3097 | -0.3586 |
| US | momentum_20d | 10581.5260 | 10581.4205 | 0.0000 | 3.0863 | -0.1054 |
| US | pure_momentum | 10812.3879 | 10832.9826 | 3998.2000 | 1.8000 | 20.5947 |
| US | momentum_volatility | 10812.3879 | 10832.9826 | 3998.2000 | 1.8000 | 20.5947 |

## Real inputs and privacy

Existing located historical daily files provide session labels without the required verified availability/execution clocks, complete lots or causal FX. They remain blocked. A historical 20-stock inventory document is not an immutable dataset receipt. No synthetic clock is attached to real data, and no missing dataset is replaced with a fixture.

The public export audit also removes unnecessary organizer/partner marketing descriptions and private onboarding guidance from current reader documents. Public rule-source links and the already-public GitHub repository identity remain for traceability. This is selective disclosure reduction, not complete anonymity. Credentials, personal contacts, account/report data, private paths and licensed raw observations belong outside source. Historical PR refs may retain previously published material; this task does not rewrite history or promise cache removal. A private audit report records that residual scope.
