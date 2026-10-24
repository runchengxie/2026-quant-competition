# Retrospective daily study

The 318 fixed daily backtests completed across US stocks, Hong Kong stocks and crypto. Their results describe separate historical windows in current fixed pools. Future performance and execution readiness remain unproven.

This optional study compares fixed strategies on immutable daily snapshots. Historical index membership has not been reconstructed, and the strategies have not been accepted for execution. Original engines, the 24-result snapshot and the expanded daily snapshot retain their original accounting and results.

## Inputs and strategies

Stock inputs require complete `competition.dataset_manifest.v2` IBKR daily snapshots, an exchange-session grid, USD for US or HKD for HK, and a separate SPY or 2800 benchmark. TRADES prices are split adjusted, not dividend total returns. The crypto path consumes Binance spot USDT daily candles. A partial parent archive is allowed only through a hash-bound, verified contiguous selected slice starting no earlier than 2023-01-01. This does not change the parent's partial status. No raw data is published.

| Market | Fixed strategies | One-way fee assumptions |
| --- | --- | --- |
| US | buy_hold, daily equal_weight, momentum_20d, sma_cross(20,60), SPY buy_hold | 20, 40 bps |
| HK | Same stock methods, 2800 buy_hold benchmark | 30, 60 bps |
| Crypto | buy/hold-like equal_weight, momentum_63d, trend_200d | 0, 10, 25 bps |

Stock momentum selects positive 20-session momentum, then equally weights eligible names. It does not rank stocks by momentum strength. SMA selects a short average above the long average. Crypto momentum requires a positive trailing 63-day return; trend requires the previous completed close above its trailing 200-day average. Eligible products receive equal weights; no eligible product means cash. At most 10 stock positions or 20 crypto positions, with gross exposure at most 1, no leverage, no turnover cap and no optimization. Stock pools larger than 10 use the first 10 eligible sorted product identifiers.

## Accounting and interpretation

Each independent fold uses 252 feature-only warmup observations, followed by 63 scored exchange sessions for stocks or 90 calendar days for crypto. Only full, nonoverlapping scoring windows are included. Every fold starts in cash. Signals use the preceding completed close. `lagged_close_proxy` assumes allocation at that preceding close; it is an idealized daily proxy, not a verified executable fill schedule. The first scored entry pays costs and there is no terminal liquidation.

The explicit `self_financing_daily.v1` path marks quantities to prices and charges actual traded notional. It solves post-fee wealth as `E_after = E_before - fee * sum(abs(weight * E_after - current_holding_value))`. This keeps fully invested entry fees cash funded. Legacy paths have different target-weight turnover and fee conventions; their historical output is preserved rather than silently replaced.

Net and zero-fee gross shadows use the same target rules. Return is final normalized wealth minus 1. Cost drag is gross return minus net return. Drawdown is a nonnegative peak-to-trough fraction, including initial wealth 1. Volatility and zero-risk-free Sharpe use sample daily standard deviation and annualization 252 or 365. Zero volatility gives null Sharpe. Costs sum normalized wealth units; turnover sums actual one-way traded notional divided by pretrade wealth. Benchmark excess return is a difference in same-fold, same-cost returns, not alpha. Never compound independent folds into a continuous portfolio.

Mean marked exposure, mean daily one-way turnover and flat-day count are daily-model eligibility proxies. All scoring dates count in the denominator. A flat day requires zero end exposure and no modeled trade. These proxies cannot establish organizer eligibility or capture intraday trading evidence. Current pools introduce selection bias; dividends, tax, financing, discrete lots, capacity, spreads and verified slippage remain unmodeled beyond the stated fee assumptions. Actual account/product authorization remains separate.

## Reproduction

Use an editable checkout for source identity and install the locked offline team profile. Root tools dispatch independent leaf CLIs and consume versioned artifacts. They never import leaf Python. Version 1 evaluation remains unchanged.

```sh
python -m competition_tools.team evaluate --config /external/team.toml --spec /external/study-spec.json --output-root /external/new-study
python -m competition_tools.check_study_delivery --config /external/team.toml --output-root /external/new-synthetic-contract
```

The v2 spec has exactly `schema`, `manifests` and `costs`:

```json
{"schema":"competition.evaluation_spec.v2","manifests":["/external/dataset/manifest.json"],"costs":{"US":[20,40],"HK":[30,60],"crypto":[0,10,25]}}
```

The immutable private plan binds input and source hashes, code commit, jobs, dates, costs and methods before execution. Maximum 384 jobs and 3600 seconds. Each leaf writes `competition.daily_study_result.v1` and private `periods.json`; root verifies identities and hashes. Changed or unavailable inputs are blocked with null metrics. Results remain `accepted_research=false`. Public output is a separate allowlisted projection, never raw period positions or private logs.

## Observed run, 2026-10-21

All 318 frozen jobs completed: US 110 (11 folds), HK 100 (10 folds), crypto 108 (12 folds). US input has 953 sessions and 10,483 bars; HK has 933 sessions and 10,263 bars, each with 10 stocks plus a benchmark from 2023-01-03 through 2026-10-20. Crypto uses 10,952 selected bars for 8 products from 2023-01-01 through 2026-09-30. Its broader requested archive remains partial; this selected interval was verified complete. Incomplete trailing scoring windows are excluded.

Both stock markets completed a bounded overlap refresh with no observed revisions; parent snapshot hashes stayed unchanged. This overlap check cannot certify older adjustment consistency. Closed-session zero-volume flat placeholders are retained raw and audited separately, never treated as trading sessions.

The table summarizes independent fold returns: median net return, median paired excess return, and the largest within-fold drawdown. These are not annual returns or a stitched equity curve. Median excess is calculated from paired differences and need not equal the difference of medians. Full per-fold facts, fees, Sharpe and eligibility proxies are available in the [Pages study section](https://runchengxie.github.io/2026-quant-competition/#study).

| Market | Strategy | One-way bps | Folds | Median net return | Median excess | Largest fold drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| US | `benchmark_buy_hold` | 20 | 11 | 4.04% | 0.00% | 17.71% |
| US | `benchmark_buy_hold` | 40 | 11 | 3.83% | 0.00% | 17.71% |
| US | `buy_hold` | 20 | 11 | 6.53% | 2.06% | 17.83% |
| US | `buy_hold` | 40 | 11 | 6.31% | 2.05% | 17.83% |
| US | `equal_weight` | 20 | 11 | 7.15% | 1.88% | 18.03% |
| US | `equal_weight` | 40 | 11 | 6.76% | 1.75% | 18.10% |
| US | `momentum_20d` | 20 | 11 | 0.35% | -4.55% | 22.36% |
| US | `momentum_20d` | 40 | 11 | -3.80% | -8.54% | 26.13% |
| US | `sma_cross` | 20 | 11 | 3.63% | 0.78% | 18.01% |
| US | `sma_cross` | 40 | 11 | 2.77% | 0.12% | 18.43% |
| HK | `benchmark_buy_hold` | 30 | 10 | 3.42% | 0.00% | 20.10% |
| HK | `benchmark_buy_hold` | 60 | 10 | 3.11% | 0.00% | 20.10% |
| HK | `buy_hold` | 30 | 10 | 4.58% | 1.37% | 21.31% |
| HK | `buy_hold` | 60 | 10 | 4.27% | 1.36% | 21.31% |
| HK | `equal_weight` | 30 | 10 | 3.78% | 0.92% | 20.55% |
| HK | `equal_weight` | 60 | 10 | 3.28% | 0.72% | 20.58% |
| HK | `momentum_20d` | 30 | 10 | -0.81% | -6.07% | 25.01% |
| HK | `momentum_20d` | 60 | 10 | -7.65% | -13.11% | 31.63% |
| HK | `sma_cross` | 30 | 10 | 2.81% | -0.55% | 20.55% |
| HK | `sma_cross` | 60 | 10 | 0.76% | -2.13% | 20.58% |
| crypto | `equal_weight` | 0 | 12 | -0.08% | 0.00% | 41.65% |
| crypto | `equal_weight` | 10 | 12 | -0.18% | 0.00% | 41.65% |
| crypto | `equal_weight` | 25 | 12 | -0.33% | 0.00% | 41.65% |
| crypto | `momentum_63d` | 0 | 12 | 2.12% | -1.86% | 45.02% |
| crypto | `momentum_63d` | 10 | 12 | -0.12% | -3.54% | 47.06% |
| crypto | `momentum_63d` | 25 | 12 | -3.38% | -6.00% | 49.98% |
| crypto | `trend_200d` | 0 | 12 | 0.95% | 1.03% | 41.09% |
| crypto | `trend_200d` | 10 | 12 | 0.66% | 0.83% | 42.24% |
| crypto | `trend_200d` | 25 | 12 | 0.22% | -0.74% | 43.93% |

Stock buy-and-hold/equal-weight baselines deserve priority over the current frequently switching 20-day positive-momentum filter. That filter loses materially more under the higher fee scenario. SMA is a separate lower-frequency candidate, with mixed relative results across markets. The crypto 200-day trend filter has a positive median paired excess at 10 bps, but not at 25 bps, and substantial drawdowns. This is insufficient evidence for deployment or an optimized winner. Next evidence should be a frozen forward Paper observation period and realistic execution/eligibility checks, rather than selecting parameters after seeing these results. The archived maker lane was not rerun because its event inputs/model were unchanged.

Reproducibility identities are published in `site/src/data/real-data-study.v1.json`. The source commit is `7b0ceae3007658e7973b26c80318f30c94696ec9` and the frozen plan SHA-256 is `4e7e31ed96ad3d734ad190b59a4d8787f7bcfc1cc0c9536360818f2346e005cc`. Private plans, input locators, period artifacts and logs remain outside Git. Projection rechecks the private plan, normalized input hashes, result identities and period artifact hashes, then copies only reviewed fields. No broker identity or registration evidence is published.

## Validation and remaining tooling issue

Local checks passed: root 682 tests (45 inherited dependency warnings), equity 158 tests, crypto 205 tests, 19 real-CLI synthetic vectors, Ruff, configured format/lock checks, public JSON Schema, Pages content/privacy gate and 10 browser tests covering locale/theme/mobile behavior. Both earlier result snapshots match the clean base checkout byte for byte. The local build ran from an external source mirror on the data drive because Astro’s intermediate asset rename cannot cross drives; no default build configuration changed.

The initial 2026-10-21 `npm audit` reported one high-severity Vite launch-editor dependency finding (GHSA-698v-4r3x-3vcv, GHSA-r825-w8mm-5pxw and GHSA-587h-7wmj-h5pm). A subsequent security maintenance update changed the locked Vite from 8.3.1 to 8.3.4 and updated its required PostCSS dependencies. A fresh explicit audit reported zero known vulnerabilities; the static build, 10 browser tests and Pages content gate passed. Earlier TLS failures and the original finding remain historical evidence. No dedicated type or coverage threshold is configured, and no additional scan is claimed. CI and deployment results are recorded in the publishing PR.

## Interactive site and documentation

The [performance dashboard](https://runchengxie.github.io/2026-quant-competition/#performance) uses Apache ECharts with market, strategy, fee and independent-window selectors. Hover, legends, curve zoom and reset are presentation controls. Published financial metrics are selected from the frozen study; the browser does not rerun accounting or join windows into a continuous portfolio. Return histograms calculate bin counts only.

The original eight views cover net/gross NAV, drawdown, window net/excess returns, fixed-window cost sensitivity, return/drawdown comparison, daily turnover and position proxies, and window-return distribution. The same currencies and methods apply across languages and themes. Accessible summaries and the complete tables remain available without JavaScript.

`competition.public_study_series.v1` contains 276 portfolio curves, derived from verified private period artifacts, plus 42 explicit unavailable records for single-instrument stock benchmarks. A curve starts at normalized wealth 1 on the last warmup close and includes each scored period. Its final net/gross wealth and largest drawdown must match the reviewed summary within 1e-10. Only dates, aggregate net/gross NAV and aggregate drawdown are published. No raw prices, individual holdings, account amounts, logs or private locators are copied. Benchmark window returns remain public; daily benchmark price-linked curves are not published.

```sh
python -m competition_tools.evaluation.study_series --aggregate /external/study/run/study-results.json --output /external/new-public-series.json
```

The [integrated documentation](https://runchengxie.github.io/2026-quant-competition/docs/) renders this canonical Markdown and the curated architecture, quickstart and dataset guides directly through Astro. Language switches retain the article. Other source documents remain GitHub links. This avoids a second documentation copy or MkDocs deployment.

Current charts describe strategy effects. IC, rank-IC, quantile spreads, decay and machine-learning out-of-time performance have not been measured. Factor/ML checks and a possible runtime adapter remain later research. Fixed slower stock schedules and crypto risk overlays now have a separate versioned ablation path described below. The default packages remain standalone. No external runtime has been connected and no new strategy experiment was run for this display update.

### Reading the research overview

The homepage lists every strategy at each market's predeclared nonzero one-way cost (US 20, HK 30, crypto 10 bps), with independent window counts, strictly positive benchmark-excess frequency, median net return and worst net return. The selected strategy panel also shows median excess return and median cost drag. Missing benchmark values are excluded from the excess denominator; zero excess is not positive. These descriptive statistics do not compound windows or constitute a significance test. Strategy descriptions distinguish stock daily equal-weight rebalancing from crypto initial equal-weight holdings with drifting weights.


### Matched strategy and fee comparisons

The dashboard adds a net NAV overlay and side-by-side metric table for the primary strategy and up to two alternatives. Market, fee, exact scored window, currency, plan and accounting basis must match. Missing results remain unavailable; curves additionally need identical date grids. Single-instrument stock benchmark daily curves remain withheld.

Fee robustness summarizes the primary strategy at all declared fees using only windows with matching input and accounting conditions at every fee. The zero-bps crypto control is explicitly labeled. Positive net and positive excess counts have separate denominators; absent benchmark values are not zero. The [strategy guide](strategies.md) documents signals, fixed pools, failure cases and reproduction. These views reuse the frozen results and do not constitute a new strategy experiment.

## Versioned ablation replay

The separate v3 evaluation path replays original controls plus fixed stock frequency and crypto trend overlays. The full matrix is 678 jobs: 318 original controls, 252 stock frequency jobs and 108 crypto overlay jobs, including 36 post-hoc 60% exposure controls. New IDs bind the actual implementation/source snapshot, catalog, origin, inputs, windows and fees. This does not replace the original 318-row snapshot or its daily curves.

The formal run must match every original control and saved exploratory metric within absolute 1e-10, with exact integer/null semantics, before aggregate publication. Migration joins scientific conditions rather than expecting old IDs. Missing or failed tasks remain explicit, not a completed 678-job claim. See the [fixed rules and CLI](strategies.md#formal-ablation) and [forward readiness](forward-observation-readiness.md). The ablation view adds paired-net-change bars and turnover/exposure scatter plots, plus inspectable aggregate tables. No new daily series, raw inputs or broker integration is published.

### Verified formal replay

All 678 jobs completed. The 318 original controls and 360 new jobs matched 8,136 frozen metric values within absolute 1e-10; the largest difference was 1.9041e-14. A separate calculation checked 62 groups and 5,180 values with zero difference. All new jobs/results passed JSON Schema; one period artifact per method was schema-checked, 28 in total. The runner separately verified every period artifact.

| Market | Signal | Policy | bps | Windows | Median net | Median excess | Worst within-window drawdown | Median paired net change (pp) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| US | `sma_cross` | `baseline` | 20 | 11 | 3.63% | 0.78% | 18.01% | +0.00 |
| US | `sma_cross` | `weekly` | 20 | 11 | 4.95% | 2.10% | 17.73% | +0.93 |
| US | `sma_cross` | `baseline` | 40 | 11 | 2.77% | 0.12% | 18.43% | +0.00 |
| US | `sma_cross` | `weekly` | 40 | 11 | 4.42% | 1.77% | 18.10% | +1.07 |
| HK | `momentum_20d` | `baseline` | 30 | 10 | -0.81% | -6.07% | 25.01% | +0.00 |
| HK | `momentum_20d` | `monthly` | 30 | 10 | 9.08% | 1.61% | 22.18% | +10.37 |
| HK | `momentum_20d` | `baseline` | 60 | 10 | -7.65% | -13.11% | 31.63% | +0.00 |
| HK | `momentum_20d` | `monthly` | 60 | 10 | 7.86% | 0.61% | 22.63% | +15.96 |
| crypto | `trend_200d` | `baseline` | 10 | 12 | 0.66% | 0.83% | 42.24% | +0.00 |
| crypto | `trend_200d` | `hysteresis_2pct` | 10 | 12 | 0.50% | -0.89% | 41.78% | -0.15 |
| crypto | `trend_200d` | `vol_target_40pct` | 10 | 12 | 0.75% | 0.72% | 37.51% | +0.09 |
| crypto | `trend_200d` | `fixed_exposure_60pct` | 10 | 12 | 1.05% | 1.17% | 27.29% | +0.40 |
| crypto | `trend_200d` | `baseline` | 25 | 12 | 0.22% | -0.74% | 43.93% | +0.00 |
| crypto | `trend_200d` | `hysteresis_2pct` | 25 | 12 | 0.18% | -1.43% | 42.43% | -0.04 |
| crypto | `trend_200d` | `vol_target_40pct` | 25 | 12 | 0.41% | -0.19% | 39.29% | +0.19 |
| crypto | `trend_200d` | `fixed_exposure_60pct` | 25 | 12 | 0.78% | 0.14% | 28.59% | +0.56 |

Each row summarizes independent windows, not a continuous account. A paired change is the median of same-window differences, not the difference between two medians. The 60% control accounts for 36 jobs across fees and remains `post_hoc_diagnostic`; other policies are `retrospective_ablation`. This table selects the discussed comparisons; the website retains all 678 rows and all costs.

US weekly SMA and HK monthly positive-momentum decisions warrant further validation, not execution approval. The 2% hysteresis band reduced trading but lowered median excess at 10 bps from the original trend control’s 0.83% to -0.89%. The 40% volatility target reduced the worst within-window drawdown alongside lower exposure. The post-hoc 60% control also reduced drawdown, so the reduction cannot be attributed entirely to the volatility algorithm. At 25 bps, the volatility variant’s median excess was -0.19%, leaving weak cost-robustness evidence.

The public aggregate is `site/src/data/ablation-study.v1.json`, with UTC `as_of` 2026-10-21. Executed source: `0952d35a6819442fade139ced03f903af7e2a9c9`. Plan SHA-256: `df7e440cad9e3bc41c413495ee61ed6fcd91992200e52ba9fdffd8f09d0148bb`. The original 318-row snapshot and existing daily curves remain byte-identical. Private inputs, retained source, periods and logs stay outside Git. No fresh data, forward sample or broker connection was added.
