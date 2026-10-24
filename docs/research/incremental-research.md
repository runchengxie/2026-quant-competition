# Reversal, learned signals and weekly crypto trading

The extra features added little to Ridge in this sample. Weekly crypto trading reduced turnover and improved results against daily trend in most windows. Its advantage over equal-weight controls remains unclear. These are retrospective comparisons on previously studied data.

## US ranking results

Each monthly pool contains at most 500 source candidates selected using the preceding 20 complete XNYS sessions. The frozen export has 658,472 candidate-days, covering 2025-09-25 through 2026-10-20. Historical security identities and types remain incomplete. This is not a certified historical common-stock or index universe.

The target is the next exact exchange session's observed last usable RTH trade divided by its first usable RTH trade, minus one. Missing next-session labels stay missing. Prices do not represent official auctions or verified order fills. The feature timestamp is an unverified bar-close availability proxy.

Simple reversal negates today's intraday return. A positive Rank IC means candidates ranked higher generally had higher next-session intraday returns. It measures ordering, with tied ranks averaged. It does not measure portfolio profit.

| Model | Jul 27–Aug 21 | Aug 24–Sep 21 | Sep 22–Oct 19 | Mean over 60 dates |
| --- | ---: | ---: | ---: | ---: |
| Simple reversal | 0.016285 | 0.000497 | 0.069205 | 0.028662 |
| Ridge, six features | 0.020962 | −0.000037 | 0.064979 | 0.028635 |
| Ridge, today's return only | 0.016285 | 0.000497 | 0.069205 | 0.028662 |
| Ridge, five other features | 0.004375 | −0.010123 | 0.004021 | −0.000576 |
| Shallow boosting tree | 0.012298 | 0.017525 | 0.006387 | 0.012070 |

All dates are in 2026. Each block requests 20 sessions. Scored candidate-days are 10,000, 10,000 and 9,954. Different identities across whole blocks number 539, 531 and 526 because monthly membership rotates. Every daily pool remains capped at 500. The final block retains 46 missing labels.

Ridge with one feature produced exactly the reversal ordering in all three blocks. Full Ridge beat reversal on 30 of 60 dates and averaged slightly below it. Removing today's return left very little ranking information. The tree beat reversal on 34 of 60 dates, yet its mean IC was lower. Daily win counts and the size of differences describe different properties.

The public table also retains zero prediction and today's return ranking. Zero prediction has no defined IC because every score is equal. Return-prediction MSE is reported for trained models and zero prediction. The two raw ranking rules have no calibrated-return MSE claim.

## Fixed predictive protocol

Use the existing optional `predictive` profile with scikit-learn 1.7.2. Each expanding outer training period has at least 126 calendar dates before its test block. Its final 20% of calendar dates is inner validation. A training label must end strictly before the following decision boundary. All candidates on a date remain together. Imputation and Ridge scaling learn only from training data.

Ridge tests alpha 0.1, 1 and 10 for three feature sets, then refits each selected setting once per block. The sets are all six original features, `session_return` alone, and the other five. The six features are `session_return`, `range_fraction`, `relative_dollar_volume`, `median_spread`, `quote_fraction` and `active_fraction`.

The tree is `HistGradientBoostingRegressor` with squared-error loss, learning rate 0.05, 100 iterations, at most 7 leaves, minimum leaf size 100, L2 penalty 1.0, 63 bins and random state 42. Only maximum depth 2 or 3 is selected. Early stopping is disabled, so random validation cannot replace the chronological split. Its median imputer learns from training data. All three blocks selected depth 3.

Inner selection maximizes equal-date mean IC with at least 20 valid dates and 30 distinct candidates per date. IC ties within 1e-12 use lower mean daily MSE, then declaration order. Missing/constant groups remain unavailable. The actual run used 45 fits, one worker and at most two native threads, with a 1,200-second subprocess limit. Attempts are recorded before fitting. There is no automatic retry or expanded grid.

Month, prior-dollar-volume terciles and spread terciles are descriptive comparisons fixed before running. Terciles use each feature date's full eligible pool, before filtering unavailable future labels. A regression check found the first implementation used only labeled rows to determine these boundaries. The correction recomputed descriptive groups from the frozen input and the 12 saved prediction files, with zero extra fits. Original reports remain private and preserved. Model predictions and whole-block results did not change. Coefficient signs and group comparisons do not establish causal effects.

## Crypto costs and less frequent trading

Use the same eight fixed spot coins and twelve independent windows as the previous controls. Each window has 252 warmup days and 90 scored days. The original frozen manifests and eight input files were verified before exporting the new input batch. This does not certify a point-in-time crypto universe.

The strict trend rule selects coins above their 200-day average and caps total allocation using a 40% annualized volatility target. It uses no leverage. Weekly trend initializes once, then rebalances on Monday UTC decision dates. On other days it holds actual units and cash. Signal and risk changes can wait until Monday, increasing between-rebalance risk. Decisions use that day's close as a price/availability approximation, followed by the next daily return.

Five account arms are retained at total one-way costs of 35 and 50 bps. The costs are scenario assumptions, not a venue fee schedule. A 35 bps cost takes 0.35% of each traded amount.

| Arm | Adjustment rule | Comparison boundary |
| --- | --- | --- |
| Daily trend | Daily strict trend targets | Existing reference |
| Daily matched equal weight | Daily, equal weight at daily trend target exposure | Coin selection under daily rebalancing |
| Weekly trend | Initial allocation, then Monday | Less frequent trend trading |
| Weekly calendar-matched equal weight | Same scheduled dates and target total allocation as weekly trend | Realized exposures may drift apart |
| Weekly exposure-matched equal weight | Daily match to weekly trend's current post-decision gross exposure | More frequent trading than weekly trend |

The last control uses exposure known at the current decision, before the next return. Neither control matches exposure, turnover and every risk at once. The site includes realized mean exposure and turnover so these differences stay visible.

| Comparison | One-way cost | Weekly trend wins | Median paired return change |
| --- | ---: | ---: | ---: |
| Versus daily trend | 35 bps | 7/12 | +2.512 percentage points |
| Versus daily trend | 50 bps | 8/12 | +2.879 percentage points |
| Versus calendar-matched equal weight | 35 bps | 5/12 | −0.383 percentage points |
| Versus calendar-matched equal weight | 50 bps | 5/12 | −0.475 percentage points |
| Versus exposure-matched equal weight | 35 bps | 5/12 | −0.268 percentage points |
| Versus exposure-matched equal weight | 50 bps | 5/12 | −0.326 percentage points |

Mean cumulative turnover fell from about 9.78 times under daily trend to 4.02 under weekly trend. Each trade is divided by account value at that decision, then these ratios are summed. Weekly trend's mean net return across windows rose from 10.62% to 13.48% at 35 bps and from 9.02% to 12.81% at 50 bps. These are averages of separate 90-day accounts, not annual returns or a stitched portfolio. The existing daily baseline was reproduced without changing its historical snapshot.

All 120 net accounts and 120 corresponding zero-cost accounts completed within the 600-second batch limit. Fees, cash-funded holdings and NAV are recomputed per cost. Gross accounts run the same policy at zero cost; drift and exposure-matched controls are recomputed for that account. Cost drag therefore describes the policy's cost scenario, including its resulting path. Daily bars do not prove depth, slippage, capacity or maker fills. USDT is not USD.

## Reproduction and publication

Set an absolute `DATA_ROOT` and a separate `UV_PROJECT_ENVIRONMENT`. New runs need an owner-scoped reservation bound to protocol, input hash, code, lock and output. The same protocol/input cannot acquire a new budget by changing its output or code. Existing or uncertain starts are refused. The checked-in results are immutable reference measurements, not permission to rerun consumed reservations.

```powershell
cd research/equity-lab
uv sync --locked --group dev --extra predictive
uv run --locked --extra predictive python -m equity_lab.predictive.incremental_cli --help
```

```powershell
cd research/crypto-mm
uv sync --locked --group dev
uv run --locked python -m crypto_mm.daily.weekly_cli --help
```

Both CLIs require `--input`, `--output` and `--reservation`. Root orchestration uses subprocesses and versioned files. It never imports research packages. The new public `incremental-research.v1.json` holds only aggregate facts. Root validation checks fields, counts, date grids, paired-account identities, finite values and the exact reviewed canonical hash. Both language versions render the same checked facts. Private predictions, raw inputs, coefficients and local receipts stay outside Git.

The candidate for future manual observation remains an inactive proposal. It includes simple reversal and full Ridge comparisons, and weekly trend with both equal-weight controls. Model/protocol hashes, cutoffs and earliest future dates must be fixed before new data are evaluated. The tree is retained in the historical evidence; it is not promoted based on one favorable block. No scheduler or existing six-candidate registry was changed.

Formal US performance still needs dated identity/type evidence, corporate-action coverage and executable price/cost acceptance. Full-market expansion and deeper models remain later work. Existing engines, target handoff and brokerage behavior are unchanged.
