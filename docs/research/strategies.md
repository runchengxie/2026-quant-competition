# Strategy guide

Daily stock and crypto strategies and the B0–B3 maker simulations are available for offline research. Their accounting and data requirements differ. The hourly DEX signals have synthetic checks only; real-data validation remains blocked.

<a id="hourly-dex-factors"></a>
## Hourly DEX factors: real data blocked

The four fixed hourly diagnostics are implemented and tested on synthetic data. The 2026-10-22 real acquisition stopped at its first authenticated check with HTTP403. No real factor IC, group return or backtest result is available. These signals are separate from the daily strategies below and B0–B3 maker simulations.

At `t = interval_end`, `momentum_24h` is `C[t]/C[t-24]-1` and `momentum_168h` is `C[t]/C[t-168]-1`. `volume_ratio_24h_7d` divides volume summed over `t-23..t` by average daily volume in `t-191..t-24`, which is that 168-hour sum divided by seven. `momentum_volume_24h` keeps positive 24-hour momentum when that ratio exceeds one, otherwise zero. Missing windows and zero volume baselines remain unavailable.

Forward labels are `C[t+h]/C[t]-1` for `h=6,24`. Every feature and label needs a complete hourly grid. Future candles cannot change earlier features. Before acquisition the protocol fixes signals, horizons, current asset identities and three 30-day slices, without parameter search. Exact scientific source bytes are hash-bound; replay requires retained or matching installed files.

Time-series rank IC is Pearson correlation of average ranks within one asset. Overall estimates need 30 pairs, each fixed slice 20. Constant signals or targets return null with a reason. `all_valid` includes overlapping labels. `non_overlapping` uses UTC hour offset from protocol start modulo the horizon; it does not establish statistical independence.

Cross-sectional diagnostics require nine distinct underlyings at the same valid timestamp. Three bins use normalized average rank `(rank-0.5)/n`, never split ties, and each need three assets. Otherwise groups return null. Group mean forward returns and top-minus-bottom spreads are gross descriptive labels, not portfolios, executable profit or fee-adjusted returns. There is no significance or out-of-sample claim. Group-return and IC denominators are separate. A constant forward-return cross-section keeps its valid group returns but contributes no IC. `ic_valid_timestamps`, `ic_excluded_reasons` and `ic_reason` explain the correlation sample and null result; undefined IC is never replaced with zero.

`competition.dex_factor_result.v1` binds protocol, manifest and input hashes, with sample counts and restrictions. Source mutation invalidates results. Public projection excludes raw data, account metadata and private paths. Unverified publication rights yield `competition.public_dex_factors.v1` with `status=readiness_only` and no metrics. See [data access and commands](datasets.md#dexpaprika-hourly-pilot).

## Daily strategy comparisons

These strategies are fixed daily research comparisons, not approved execution strategies. Read the [study methods](real-data-study.md) and [dataset contract](datasets.md) before interpreting results. The homepage links each strategy to this guide and compares only a common market, fee and scored window.

## Shared assumptions and evidence

The daily assumptions in this section do not apply to the separate hourly diagnostics described below.

The frozen 2026-10-21 study contains 318 completed strategy/window/cost jobs. Stocks use 63 scored trading periods per window, crypto uses 90 daily periods, each after 252 warmup periods. Windows restart from cash independently. Input pools are fixed current selections, not point-in-time historical index membership. The US pool has ten instruments, HK ten and crypto eight. Dataset identity, coverage, adjustment and selection limitations are documented in the study, not inferred from a strategy name.

Signals use the prior close and holdings earn the next close-to-close move. The model is long-only and cash-funded. Initial entry incurs costs; final holdings are not liquidated. Stock periods annualize at 252 and crypto at 365. Dividends, taxes, financing, discrete lots, capacity and independently verified execution slippage are not modeled beyond the declared fees. No strategy here connects to a broker or establishes competition eligibility.

The fixed one-way cost assumptions are US 20/40 bps, HK 30/60 bps and crypto 0/10/25 bps. Zero cost is a control. The homepage defaults to nonzero 20/30/10 bps. Use the fee summary to compare the same windows at every declared fee, including the zero-cost control. Missing benchmark values are excluded from the positive-excess denominator; zero excess is not a win. These are descriptive statistics, not significance tests or new out-of-sample evidence.

<a id="buy-hold"></a>
## Buy and hold: `buy_hold`

Stock research initially allocates equally across up to ten instruments in sorted identifier order, then lets weights drift with prices. It does not rebalance back to equal weights daily. Its main risks are market declines, concentration from drifting weights and a selected current pool. A positive window return alone does not establish benchmark outperformance.

Implementation: [stock study](../../research/equity-lab/src/equity_lab/study/run.py). Compare with `equal_weight` under the same market, window and fee to inspect rebalancing effects.

<a id="equal-weight"></a>
## Equal weight: `equal_weight`

For stocks, each daily decision equally weights up to ten sorted instruments. For crypto, the fixed spot pool is initially equal-weighted and then held with drifting weights. The same identifier therefore describes different allocation rules across these separate experiments. Crypto `equal_weight` is also the declared benchmark, so its excess against itself is zero.

Stock rebalancing can add turnover and cost drag. Neither implementation protects against broad market declines. Compare only within the same market. Implementations: [stocks](../../research/equity-lab/src/equity_lab/study/run.py) and [crypto daily study](../../research/crypto-mm/src/crypto_mm/daily/study.py).

<a id="momentum-20d"></a>
## Positive momentum over 20 sessions: `momentum_20d`

The stock model selects instruments whose prior-close return over 20 sessions is strictly positive. It takes up to ten qualifying instruments in sorted identifier order and weights them equally, or holds cash when none qualify. This is a sign filter, not cross-sectional momentum ranking. Targets can change daily.

Near-zero signals can switch repeatedly and increase costs. The filter can lag sudden reversals and miss rebounds after a decline. Inspect turnover, fee sensitivity and the worst window alongside median return. Sources: [signal](../../research/equity-lab/src/equity_lab/signals/momentum.py) and [allocation](../../research/equity-lab/src/equity_lab/study/run.py).

<a id="sma-cross"></a>
## Moving-average filter: `sma_cross`

At the prior close, the stock model selects instruments whose 20-session average is strictly above their 60-session average. It takes up to ten in sorted identifier order, equally weights them and holds cash when none qualify. This is a daily state filter, not an intraday crossover fill model.

Sideways prices can cause repeated position changes, while delayed signals can miss the start of a rebound. Compare against hold and equal-weight baselines at both declared stock fees. Sources: [signal](../../research/equity-lab/src/equity_lab/signals/sma.py) and [allocation](../../research/equity-lab/src/equity_lab/study/run.py).

<a id="benchmark-buy-hold"></a>
## Stock benchmark: `benchmark_buy_hold`

This holds the predeclared single-instrument stock reference. It is a comparison baseline, not a recommended portfolio. Its window returns remain public, but daily normalized benchmark curves are deliberately withheld because they are price-linked. The comparison table can therefore show a benchmark result without adding a benchmark line.

The benchmark does not recreate the selected stock pool, and its own benchmark excess is zero. Consult [study evidence](real-data-study.md) for the benchmark and pool definitions.

<a id="momentum-63d"></a>
## Positive crypto momentum over 63 daily periods: `momentum_63d`

The daily spot model equally weights assets whose prior close exceeds their close 63 daily periods earlier, and holds cash if none qualify. This is positive trailing return selection, not ranking, shorting or a derivative strategy.

Frequent changes near the threshold can incur costs. Volatility and sharp reversals can dominate results. Inspect the same-window comparison and the matched-window fee summary. Implementation: [crypto daily study](../../research/crypto-mm/src/crypto_mm/daily/study.py).

<a id="trend-200d"></a>
## Crypto 200-period trend filter: `trend_200d`

The daily spot model equally weights assets whose prior close is strictly above their trailing 200-period average, or holds cash if none qualify. This original control does not scale positions by volatility or use a turnover buffer. The separate versioned ablation path below adds fixed overlays without changing this control.

The filter can lag reversals and repeatedly enter or exit near the moving average. Lower exposure does not guarantee a smaller drawdown. Inspect worst windows and higher-fee outcomes rather than selecting one favorable curve. Implementation: [crypto daily study](../../research/crypto-mm/src/crypto_mm/daily/study.py).


<a id="formal-ablation"></a>
## Formal ablation policies

The separate `competition.evaluation_spec.v3` path makes the fixed frequency/risk experiments reproducible. It preserves `self_financing_daily.v1`, independent cash starts, original fees, warmup and scoring lengths. Original v1 jobs and the 318-row published study remain unchanged. New jobs/results use v2 identities that bind policy parameters and provenance. A formal rerun is still retrospective evidence.

| Market | Base signal | `variant_id` | Rule |
| --- | --- | --- | --- |
| US/HK | `equal_weight`, `momentum_20d`, `sma_cross` | `weekly` | First observed decision close of each ISO week |
| US/HK | Same three signals | `monthly` | First observed decision close of each calendar month |
| crypto | `trend_200d` | `hysteresis_2pct` | Enter above 1.02 × SMA200, exit below 0.98 × SMA200, retain state between thresholds |
| crypto | `trend_200d` | `vol_target_40pct` | Previous 20 complete selected-basket returns, sample deviation × sqrt(365), multiplier min(1, 0.40 / volatility) |
| crypto | `trend_200d` | `fixed_exposure_60pct` | Multiply the original trend target weights by 0.60 |

Stock initial entry always occurs on the first scored decision. Other decisions use the prior close. Between scheduled decisions, the model holds actual quantities and cash rather than rebalancing yesterday's weights. Crypto hysteresis warms state from the first complete 200-period mean. Volatility uses the currently selected equal-weight basket with no future returns; zero volatility gives multiplier 1 and an empty selection holds cash. No overlay adds leverage. The 60% rule targets 40% cash immediately after an invested allocation; later marked exposure can exceed 60%.

All original base strategies remain explicit `baseline` controls. Frequency rules and the first two crypto overlays carry `retrospective_ablation`: parameters were fixed before their probe, after earlier historical results were seen. The 60% control carries `post_hoc_diagnostic` because it was chosen after inspecting that probe. Refreezing, filtering or translating a result cannot change its evidence role. This does not establish statistical significance, an optimal parameter or unseen-sample performance.

The v3 specification requires `schema`, `manifests`, `costs`, `variants` and `origin`. Each selected market must include every original strategy with `variant_id: baseline`; additional catalog pairs are explicit. `origin` supplies external `probe_protocol`, `diagnostic_protocol` and `evidence_manifest` paths. The diagnostic must hash its parent protocol, and the manifest must hash both protocols and its listed evidence. Parameter overrides and unknown fields fail. This is an explicit import of experiment provenance, not automatic discovery of private paths.

```sh
python -m competition_tools.team evaluate --config /external/team.toml --spec /external/ablation-spec.json --output-root /external/new-ablation
python -m competition_tools.evaluation.ablation_publication --aggregate /external/new-ablation/run/study-results.json --output /external/new-public-ablation.json
python -m competition_tools.check_ablation_delivery --config /external/team.toml --output-root /external/new-synthetic-ablation
```

Use a committed checkout and newly named external outputs. The last command creates its own explicitly synthetic inputs and origin evidence, so it needs no private research archive. Root and both leaf environments must resolve to this checkout. Source snapshots retained beside the private run allow later verification after the development worktree is removed. The new plan cap is 768 jobs with one shared 3600-second deadline and batches of at most 384; the original plan cap remains 384. Failed/blocked jobs keep null metrics and explicit reasons, with no automatic retry.

The [ablation section](https://runchengxie.github.io/2026-quant-competition/#ablation) uses the separate `competition.public_ablation.v1` aggregate. It groups independent windows by market, currency, signal, policy and cost. Paired differences use the same exact window and fee against the original control, not the difference between unrelated medians. Missing counterparts stay null. Charts and filters do not recalculate accounting, publish raw input prices or add new daily curves.

<a id="forward-observation"></a>
## Before forward observation

The [new controls programme](strategy-controls.md) completed 420 retrospective jobs under a separate protocol. Its 420 aggregate result rows and 224 matched comparisons are now published under the project owner-confirmed display authorization. The six US/crypto candidates were fixed before that run in the [manual observation registry](observation-registry.md). At the 2026-10-23 snapshot, no real forward observation has been accepted. Fresh complete warmup and reviewed availability evidence are still required; cached tails remain retrospective. The [execution model](us-execution-evidence.md) separately requires compatible raw prices, action and lot/listing evidence. No collector, scheduler, broker login or order route was activated. See the [current readiness checklist](forward-observation-readiness.md).

## Reproduce and inspect

First follow the [team quickstart](../operations/team-quickstart.md) for an editable checkout and the locked offline profile. Real-data replay needs authorized immutable dataset manifests, the external team configuration and a v2 study specification. The root command runs the fixed matrix of strategies supported by each manifest; it has no single-strategy flag. A new source commit or different inputs produce a new research identity, not an exact reconstruction of the original artifact hashes.

```sh
python -m competition_tools.team evaluate --help
python -m competition_tools.team evaluate --config /external/team.toml --spec /external/study-spec.json --output-root /external/new-study
python -m competition_tools.evaluation.study_publication --aggregate /external/new-study/run/study-results.json --output /external/new-public-study.json
```

Keep these paths outside the source checkout and use new output paths. The public repository does not distribute the licensed raw inputs. Use the separate synthetic delivery check to exercise the CLI contracts without claiming real-data performance:

```sh
python -m competition_tools.check_study_delivery --config /external/team.toml --output-root /external/new-synthetic-contract
```

[Open the performance dashboard](https://runchengxie.github.io/2026-quant-competition/#performance). Compare strategies at the same fee and exact window. Use fee robustness across matching windows to inspect cost dependence. Historical windows are never compounded into a continuous account. The published legacy snapshots retain their original runs; the new controls have a separate protocol and publication gate.
