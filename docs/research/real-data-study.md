# Retrospective daily study

This optional study compares fixed strategies on immutable daily snapshots. It is retrospective research with a fixed current pool, not a historical index reconstruction or an accepted execution strategy. Original engines, the 24-result snapshot and the expanded daily snapshot retain their original accounting and results.

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

Local checks passed: root 679 tests (45 inherited dependency warnings), equity 158 tests, crypto 205 tests, 19 real-CLI synthetic vectors, Ruff, configured format/lock checks, public JSON Schema, Pages content/privacy gate and 10 browser tests covering locale/theme/mobile behavior. Both earlier result snapshots match the clean base checkout byte for byte. The local build ran from an external source mirror on the data drive because Astro’s intermediate asset rename cannot cross drives; no default build configuration changed.

`npm audit` reports one high-severity Vite dependency finding, covering launch-editor advisories GHSA-698v-4r3x-3vcv, GHSA-r825-w8mm-5pxw and GHSA-587h-7wmj-h5pm. It remains unresolved in the existing lockfile. The first explicit audit attempt failed on TLS; a bounded direct retry returned this finding. Offline installation output is not treated as a successful vulnerability scan. No dedicated type or coverage threshold is configured, and no additional scan is claimed. CI and deployment results are recorded in the publishing PR.
