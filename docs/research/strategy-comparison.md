# Strategy selection, costs and execution delay

[简体中文](strategy-comparison.zh-CN.md)

The completed US intraday selection estimates all lost money at 20/40 bps one-way costs. At the original execution timing, Ridge trailed simple reversal in both comparable windows. Crypto weekly trend was sensitive to execution delay and did not show a stable advantage over its matched-target-exposure control. These are retrospective diagnostics on previously studied history.

The run completed 42 model-fit attempts, 72 equity comparison cells and 288 crypto cells. Equity has 45 complete cells and 27 unavailable cells. Crypto has 288 complete cells. Missing outcomes and constant forecasts remain visible. No extra fits or account replays were added after inspecting the results. The 72 equity cells share three windows, and the 288 crypto cells share twelve. These counts do not represent independent market samples.

## US selection and cost estimates

The frozen daily input contains 658,472 candidate-days from 2025-09-25 through 2026-10-20. Monthly eligibility uses the prior 20 complete XNYS sessions, a prior close of at least USD5 and mean daily dollar volume of at least USD10 million. The pool is capped at 500 source candidates. Historical identity, security type and source selection remain incomplete. This is not a certified S&P 500 or historical common-stock universe.

Equal weight uses every monthly candidate with usable signal-day OHLC. Pool membership follows the signal-date month. Simple reversal, Ridge and Elastic Net each select the 50 highest scores, breaking ties by candidate ID. A constant forecast has no ranking, so that account remains unavailable. Different concentration means these accounts do not isolate a model's causal contribution.

Simple reversal negates the signal day's first-to-last return, ranking the largest declines first. The learned target is the next session's intraday price return. IC measures whether scores and later returns rank in the same direction, using average ranks for ties. MSE measures squared return-prediction error. Both metrics are calculated daily and give each valid date equal weight.

Ridge and Elastic Net reuse the existing six features and grids from the [prediction protocol](equity-predictive.md). Three expanding chronological folds each request 20 signal dates. Training has at least 126 prior session labels. The final 20% of prior dates form inner validation. Labels must end strictly before the following decision boundary. Imputation and scaling fit only training data. The run used 36 validation fits and six selected refits, one worker, at most two native threads and a 1,200-second worker deadline.

| Signal dates | Original execution | Delayed execution |
| --- | --- | --- |
| 2026-07-27 to 2026-08-21 | Next exact XNYS session | One further XNYS session |
| 2026-08-24 to 2026-09-21 | Next exact XNYS session | One further XNYS session |
| 2026-09-22 to 2026-10-19 | Next exact XNYS session | One further XNYS session |

The price proxy enters at the execution session's first usable regular-session trade and sells at its last usable trade. Positions are flat afterwards. Each window starts at normalized NAV1, denominated in USD. Holdings are fractional and long-only. Official auctions, lot sizes, minimum commissions, spread/depth and executable fills have not been accepted.

For one-way fee fraction `f` and a selected portfolio's intraday price return `r`, the fully invested account factor is `(1+r)*(1-f)/(1+f)`. Entry cost is funded from available cash and exit cost applies to sale value. Fees are 0/20/40 bps per side, so daily entry and exit both incur cost. Zero cost is a counterfactual. Cumulative charged costs and the zero-cost/net return gap can differ because fees change subsequent capital.

Scores are saved for all monthly candidate rows before future-label filtering. Forecast IC/MSE use available future labels. Portfolio selection additionally requires usable signal-day prices and occurs before examining outcomes. A selected name with no usable execution-session result blocks that account. Remaining names are not renormalized. Later dates do not repair the gap, and a continuous window return stays unavailable. The delayed final window also extends beyond the retained execution calendar.

| One-way cost | Timing | Ridge above equal weight | Median paired return difference |
| --- | --- | --- | --- |
| 20 bps | Original | 2 of 2 comparable, 3 requested | +4.3621 percentage points |
| 40 bps | Original | 2 of 2 comparable, 3 requested | +4.0267 percentage points |
| 20 bps | One session later | 0 of 2 comparable, 3 requested | −3.8199 percentage points |
| 40 bps | One session later | 0 of 2 comparable, 3 requested | −3.5262 percentage points |

Relative improvement did not produce a positive net estimate. All 30 completed cells with nonzero tested costs lost money. The least negative was −3.4168%. At the original timing, simple reversal exceeded Ridge in both comparable windows at both costs. Elastic Net's first fold produced constant scores. Missing selected outcomes also block equal weight and learned models in the last fold. Some blocked cells have more than one reason, so reason counts cannot be summed as separate accounts.

## Crypto holding and trend controls

The same fixed-current eight spot coins and 12 independent windows are retained. Every window has 252 warmup days and 90 scored days, starting a separate normalized NAV1 account denominated in USDT. Windows are not joined. USDT is not converted to USD.

| Arm | Policy |
| --- | --- |
| `buy_hold_equal_weight` | Buy equal weights once, then hold units and cash |
| `fixed60_weekly` | Target 60% total allocation equally across all eight coins |
| `trend_weekly` | Existing strict 200-day trend and 40% volatility target |
| `matched_weekly` | Equal weights at trend's scheduled target total allocation |

The last three arms initialize once and then rebalance on Monday UTC decision dates. Between trades they hold actual units. A one-day delay shifts both targets and trade dates, with cash before the delayed initial trade. Fees of 0/35/50 bps are total one-way scenarios. Each net and zero-cost account is recalculated using the existing cash-funded ledger. Final holdings are marked without a terminal sale. The fixed run retained 288 net and 288 gross accounts within its 600-second worker deadline.

Trend selects coins above their trailing 200-day mean and allocates equally among them. Recent portfolio volatility controls total target exposure, with a 40% annualized target and no leverage. The strict rule stays in cash when estimated volatility is zero. This target does not guarantee realized volatility.

| One-way cost | Timing | Trend above buy and hold | Median paired return difference |
| --- | --- | --- | --- |
| 35 bps | Original | 8/12 | +5.4464 percentage points |
| 50 bps | Original | 8/12 | +5.1839 percentage points |
| 35 bps | One UTC day later | 6/12 | +1.3345 percentage points |
| 50 bps | One UTC day later | 7/12 | +1.2912 percentage points |

Buy and hold and 60% allocation have different exposure from trend. The matched weekly arm matches scheduled target exposure, not every realized weight or risk. Against this control, trend wins 5/12 windows at either nonzero cost under original timing, with median differences of −0.3830/−0.4750 percentage points. Delaying both arms gives 6/12 and +0.3809/+0.2846 percentage points. These descriptive results do not establish a stable selection edge or statistical significance. Daily prices do not establish maker fills or trading capacity.

## Concentration and input quality

The site reports the largest instrument's share of positive price PnL. Negative contributions are outside that denominator. If there is no positive contribution, the share remains unavailable. Another diagnostic replaces the five highest net-return days with cash days and recomputes compounding. Those days are selected ex post, so the diagnostic does not define a usable timing strategy.

The daily audit found zero duplicate candidate/session keys, non-session rows, nonfinite numeric values or negative dollar volume. It found 441 rows without usable OHLC, including missing prices, and 2,205 missing numeric values. Of all candidate-days, 657,731 have unresolved identity. Complete dated type/action evidence and verified feature availability remain blockers to formal trading performance.

The minute audit read one deterministic generic row group of 120,017 rows, covering 127 codes. Selected columns required about 1.09 MB compressed. The sample includes 49,530 regular-session rows. It has zero duplicate minute keys, invalid traded OHLC or regular rows outside the calendar session. There are 66,650 zero-volume rows, 62 missing quotes and 37,771 spreads above 5% across all sampled sessions. Pre/post-market rows are included. This convenience sample cannot estimate full-market quality or certify the conversion.

At the dated storage inspection, the raw daily-partition conversion and standard by-security Zstd6 layout both reported completion of 629,687,711 rows. The new delta/Zstd12 repack was still running. No data was moved or source pointer changed. The storage handoff requires its own owner-receipt acceptance, beyond this bounded sample check.

## Frozen evidence and future work

Scientific source is commit `f8761ab38fdcf83697503aef133649b11574016e`. The private plan hash is `b50fde4f1cb84161d34937b9aab034d3b07e72bbce0dcbddf0b5dba3e748189d`. The completed result hash is `8d7d5feb02627ff9f8751f7d6053193ed6c4ea3a93cc8170eb5e5d12dba2bd8c`. Exact inputs, source bytes, locks, actual environments, attempts, predictions and account periods remain in the external owned bundle. Root stdlib verification rechecks selections and outcomes from CSV exports and independently solves crypto commission funding. Source hashes bind integrity, not data authenticity or executable prices.

The prospective proposal was frozen at `2026-10-24T18:44:11.470368+00:00`. It is inactive and `awaiting_fresh_verified_data`, with no first eligible observation or certified unseen data. The existing six-candidate observation registry is unchanged. Previously inspected history cannot become a new untouched holdout. Fresh complete warmup and reviewed availability evidence are still required.

The run was offline and reused existing data. Existing model engines, historical snapshots and broker behavior remain unchanged. The new price/cost estimates are separate from accepted performance and executable targets.

## Commands and contracts

Use Python3.12 and the existing locked environments. The equity CLI requires the optional `predictive` profile. Both real-data CLIs require a source checkout with the exact lock and an approved owner-scoped reservation. The published run has consumed its reservations. Changing output or code does not grant another attempt.

```sh
python -m equity_lab.predictive.comparison_cli --help
python -m crypto_mm.daily.comparison_cli --help
python -m competition_tools.evaluation.run_record --run-root /absolute/completed-bundle
python -m competition_tools.evaluation.comparison_evidence --run-root /absolute/completed-bundle --output /absolute/new-public-candidate.json
```

Run each leaf command in its independently installed environment and root commands in the root environment. Replace placeholders with absolute paths; Windows needs drive-qualified paths. The last command only projects saved results, with no fits or replays, and refuses to overwrite an existing output. It needs the complete bundle, including the retained `source/` tree and inputs. Post-run addition of unavailable reason codes changed no scientific values and used zero additional fits or replays.

The reviewed aggregate is [strategy-comparison.v1.json](../../site/src/data/strategy-comparison.v1.json), governed by [the public schema](../../schemas/research/strategy-comparison-public.v1.schema.json) and its exact reviewed canonical hash. Both languages and all chart filters consume the same facts. Raw prices, individual predictions and private paths stay outside public Git. See [workflow checks](../operations/workflow-check.md) for receipt integrity and [manual observation](observation-registry.md) for the separate future-data gate.
