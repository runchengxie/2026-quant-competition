# Trading frequency, prediction and return attribution

[简体中文](strategy-comparison.zh-CN.md)

Keeping slightly lower-ranked stock holdings usually reduced trading, but higher returns were less common. The new Ridge and Elastic Net forecasts remain unstable. Crypto attribution shows how market returns, exposure and selection contributed along the saved account paths. All results below are retrospective price/cost research, with no accepted trading performance or new future observations.

## Latest multi-session stock experiment

The new protocol uses two signal windows, 2026-05-28 through 2026-07-24 and 2026-07-27 through 2026-09-21. Each has 40 signal dates and a common 41-session valuation grid. Portfolios rebalance every five or twenty sessions at the next exact session's first usable regular-session trade. Delaying execution adds one session. Original timing spends the final valuation session in cash, and delayed timing spends the first in cash. Each window starts a separate NAV 1 USD account. Units drift between trades, fees are cash-funded, and the terminal sale is charged.

The seven variants are equal weight and top-50 simple reversal, Ridge or Elastic Net with retention buffers of 0/20 ranks. Buffer 20 retains existing holdings still within the top 70 and fills vacancies by score. It does not filter candidates using future outcomes. Equal weight keeps its original unbuffered pool. The 0/20/40 bps one-way costs and two execution timings produce 168 requested accounts. These configurations share two historical windows.

| Prediction / rebalance horizon | One-way cost | Completed / requested | Positive net estimates | Median completed net estimate |
| --- | --- | --- | --- | --- |
| 5 sessions | 20 bps | 26/28 | 9 | −3.1385% |
| 5 sessions | 40 bps | 26/28 | 6 | −5.2604% |
| 20 sessions | 20 bps | 14/28 | 9 | +0.9830% |
| 20 sessions | 40 bps | 14/28 | 8 | +0.3442% |

Across all costs, 120 accounts completed and 48 remain unavailable. Known action boundaries block 12, unavailable model selection blocks 24, and constant forecasts block 12. Missing required prices would also block an entire account. Later dates never repair its return. The matching buffer comparisons requested 72 pairs. Of 54 comparable pairs,48 traded less and 19 returned more. Their median return difference was −0.1020 percentage points. These are repeated conditions on shared histories, not independent samples or causal estimates.

### Machine learning and label timing

The target is the raw-price return from the next exact session's first trade to the fifth or twentieth session's last trade. Every intervening session must have usable OHLC and avoid the seven known action boundaries. The six existing features, monthly source pool capped 500, training-only imputation/scaling and original parameter grids are retained. Ridge uses L2 regularization. Elastic Net combines L1 and L2 regularization. The grids select on earlier inner-validation dates, with labels ending strictly before the next decision boundary. Full scores are exported before checking future labels.

The fixed maximum was 56 fits. The run used 48 validation fits and 6 refits,54 in total. Both twenty-session models in the first fold had only 14 valid inner-validation dates after the longer-label purge, below the preset 20-date selection minimum. Neither was refitted. This limitation remains visible, with no threshold change or post-result rerun. The later twenty-session Elastic Net refit produced a constant forecast and no ranking IC.

| Model | Horizon | First-window mean daily IC | Second-window mean daily IC |
| --- | --- | --- | --- |
| Ridge | 5 sessions | −0.0583 | +0.0050 |
| Elastic Net | 5 sessions | −0.0630 | +0.0208 |
| Ridge | 20 sessions | Unavailable | −0.0298 |
| Elastic Net | 20 sessions | Unavailable | Unavailable, constant forecast |

IC compares score ranks with later return ranks. Positive values mean agreement, negative values mean opposite rankings. MSE measures squared prediction error within the same horizon. Both are calculated daily and give each valid date equal weight. This previously studied history cannot establish new out-of-sample efficacy. Historical security types, full actions, survivorship and actual feature availability remain unresolved.

### Earlier intraday cost tolerance

Read-only verification reused the earlier 24 zero-cost account cells, of which 15 completed. Six had positive gross returns and nine already lost before costs. For the six profitable cells, exact break-even one-way cost ranged from 5.0125 to 11.3087 bps, with median 6.6586 bps. Nine other cells were unavailable. With gross growth factor G and 20 daily round trips, the threshold is `10000 * tanh(log(G) / 40)`. The formula reproduces the saved 20/40 bps paths. It is specific to the cash-funded daily-flat model. The new holdings experiment has different windows, duration and accounting.

## Crypto accounting attribution

This task verifies and decomposes the existing 288 saved accounts without another crypto replay. For each day, the market reference is the simple mean of the eight coin price returns. Its contribution equals the strategy's prior NAV times that return. The exposure contribution adjusts for invested capital below prior NAV. Selection measures the contribution within invested capital relative to that reference. Costs enter negatively. Sum monetary PnL over dates and divide by initial NAV 1. The four contributions then add to net return without confusing additive PnL with compounded daily returns.

At 35 bps and original timing, the weekly trend accounts' twelve-window mean contributions were market+16.6499%, exposure−2.7401%, selection+0.9339% and costs−1.3596%, summing to+13.4841%. The windows share historical periods. These descriptive account-path components do not establish causality, selection alpha or statistical significance. The frictionless daily equal-weight reference is not a separate investable control. USD stock accounts and USDT crypto accounts remain separate.

## Identity and action evidence

The retained master and interval records cover all 658,472 candidate-days, but 657,731 candidate-days and 2,511 of 2,518 identity segments remain unresolved. The master provides 31 warrant clues, two bounded-identity candidates and one reorganization case. Those source assertions do not certify complete dated security types.

Seven issuer announcements or SEC filings were read. They concern [NFLX](https://ir.netflix.net/investor-news-and-events/financial-releases/press-release-details/2025/Netflix-Announces-Ten-For-One-Stock-Split/default.aspx), [BK/BNY](https://www.bny.com/corporate/global/en/about-us/newsroom/press-release/bny-announces-planned-change-of-stock-ticker-symbol-to-bny-130465.html), [RNA](https://www.sec.gov/Archives/edgar/data/2093101/000119312526083227/d87849d8k.htm), [BKNG](https://d18rn0p25nwr6d.cloudfront.net/CIK-0001075531/27ace9e2-033e-4276-b3cc-02b52be010fe.pdf), [KLAC](https://ir.kla.com/sec-filings/all-sec-filings/content/0001193125-26-212093/d116682dex991.htm), [AGL](https://investors.agilonhealth.com/news/news-details/2026/agilon-health-Announces-Reverse-Stock-Split/default.aspx) and [WOLF](https://www.sec.gov/Archives/edgar/data/895419/000119312525223057/d69265d8k.htm). This review confirms the sparse announcement/filing evidence, not every settlement or historical identity link. Four raw-price split boundaries match those seeds. A derived input adds seven `KnownActionBoundary` flags while preserving every original price and feature value. Labels crossing those days and accounts holding or entering affected names are quarantined, without silently adjusting prices or joining identities. The 243 large adjacent observed price jumps can include gaps and other effects. They are not 243 certified actions. Unknown actions and dividend/total-return treatment remain unresolved.

## Fresh observation status

The one-shot free daily-archive extension stopped at its frozen 300-second limit after 345 attempts and 55,656 recorded response-body bytes. Its final request was in flight, so final transfer spend is uncertain. The incomplete output has no accepted manifest. No automatic retry, resume or schedule ran. Crypto warmup remains through 2026-09-30 and US warmup through 2026-10-20. No new registry was frozen and zero prospective observations were accepted. The earlier six-candidate protocol remains unchanged, with US 20/40 bps and crypto 0/10/25 bps. New ML results do not promote themselves into that protocol or executable targets. Fresh complete warmup and reviewed availability remain prerequisites.

## Latest frozen record and reproduction

Scientific commit `da4ba95905290059a6dc07163368d0508ab090c7` binds the implementation. Plan `33e3be7e5e9d82f2b27898ca78aeacffe4b5601126bc0bc235c10d179e047a56` and result `3f44b319bfb2c1a1cb0741de1b3800b14b1621e64a47fb169eb12639d2a40534` bind the actual run. Its 54 fits and 168 net/gross pairs finished in 246.906 seconds, within a 2,400-second worker deadline and 1,200 seconds per horizon. Exact input copies, source/locks, wrapper bytes, environment metadata, attempts, predictions and periods remain external. Root stdlib verification independently checks selection, calendar timestamps, purged label counts, IC/MSE, held units, cash and terminal fees. It verifies the declared exports and integrity, without independently certifying primary Parquet decoding or provider authenticity.

The [latest aggregate](../../site/src/data/low-turnover.v1.json) has canonical hash `fa7e00c9b9582caf7c6656e5151520cde588304dc523b28953e9eeaf22d2a6e2` and a [closed public schema](../../schemas/research/low-turnover-public.v1.schema.json). The complete private parent comparison bundle is required for saved-output reproduction. No real-data CLI may repeat a consumed reservation. Use the independently installed root and equity environments.

```sh
python -m equity_lab.predictive.holding_cli --help
python -m competition_tools.check_holding_delivery --leaf-python /absolute/equity-environment/bin/python --output-root /absolute/new-synthetic-output
python -m competition_tools.evaluation.low_turnover_projection --run-root /absolute/completed-bundle --output /absolute/new-candidate.json
```

The delivery checker generates only deterministic synthetic input. The projection command only verifies saved records. Both refuse existing outputs. Windows uses drive-qualified paths and the corresponding `Scripts/python.exe`. The website groups both strategy and factor views by Hong Kong, US and crypto. Its homepage is an overview, with no combined cross-market NAV. Hong Kong retains its existing fixed-pool comparisons and pending independent factor tests.

## Earlier intraday and weekly comparison

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

The price proxy enters at the execution session's first usable regular-session trade and sells at its last usable trade. Positions are flat afterwards. Each window starts at normalized NAV 1, denominated in USD. Holdings are fractional and long-only. Official auctions, lot sizes, minimum commissions, spread/depth and executable fills have not been accepted.

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

The same fixed-current eight spot coins and 12 independent windows are retained. Every window has 252 warmup days and 90 scored days, starting a separate normalized NAV 1 account denominated in USDT. Windows are not joined. USDT is not converted to USD.

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

The site reports the largest instrument's share of positive price PnL. Negative contributions are outside that denominator. If there is no positive contribution, the share remains unavailable. Another diagnostic mechanically omits the five highest daily net returns and recomputes compounding. Holdings and fees are not recalculated. Those days are selected ex post, so the diagnostic does not define a usable timing strategy.

The daily audit found zero duplicate candidate/session keys, non-session rows, nonfinite numeric values or negative dollar volume. It found 441 rows without usable OHLC, including missing prices, and 2,205 missing numeric values. Of all candidate-days, 657,731 have unresolved identity. Complete dated type/action evidence and verified feature availability remain blockers to formal trading performance.

The minute audit read one deterministic generic row group of 120,017 rows, covering 127 codes. Selected columns required about 1.09 MB compressed. The sample includes 49,530 regular-session rows. It has zero duplicate minute keys, invalid traded OHLC or regular rows outside the calendar session. There are 66,650 zero-volume rows, 62 missing quotes and 37,771 spreads above 5% across all sampled sessions. Pre/post-market rows are included. This convenience sample cannot estimate full-market quality or certify the conversion.

At the dated storage inspection, the raw daily-partition conversion and standard by-security Zstd 6 layout both reported completion of 629,687,711 rows. The new delta/Zstd 12 repack was still running. No data was moved or source pointer changed. The storage handoff requires its own owner-receipt acceptance, beyond this bounded sample check.

## Frozen evidence and future work

Scientific source is commit `f8761ab38fdcf83697503aef133649b11574016e`. The private plan hash is `b50fde4f1cb84161d34937b9aab034d3b07e72bbce0dcbddf0b5dba3e748189d`. The completed result hash is `8d7d5feb02627ff9f8751f7d6053193ed6c4ea3a93cc8170eb5e5d12dba2bd8c`. Exact inputs, source bytes, locks, actual environments, attempts, predictions and account periods remain in the external owned bundle. Root stdlib verification rechecks selections and outcomes from CSV exports and independently solves crypto commission funding. Source hashes bind integrity, not data authenticity or executable prices.

The prospective proposal was frozen at `2026-10-24T18:44:11.470368+00:00`. It is inactive and `awaiting_fresh_verified_data`, with no first eligible observation or certified unseen data. The existing six-candidate observation registry is unchanged. Previously inspected history cannot become a new untouched holdout. Fresh complete warmup and reviewed availability evidence are still required.

The run was offline and reused existing data. Existing model engines, historical snapshots and broker behavior remain unchanged. The new price/cost estimates are separate from accepted performance and executable targets.

## Commands and contracts

Use Python 3.12 and the existing locked environments. The equity CLI requires the optional `predictive` profile. Both real-data CLIs require a source checkout with the exact lock and an approved owner-scoped reservation. The published run has consumed its reservations. Changing output or code does not grant another attempt.

```sh
python -m equity_lab.predictive.comparison_cli --help
python -m crypto_mm.daily.comparison_cli --help
python -m competition_tools.evaluation.run_record --run-root /absolute/completed-bundle
python -m competition_tools.evaluation.comparison_evidence --run-root /absolute/completed-bundle --output /absolute/new-public-candidate.json
```

Run each leaf command in its independently installed environment and root commands in the root environment. Replace placeholders with absolute paths; Windows needs drive-qualified paths. The last command only projects saved results, with no fits or replays, and refuses to overwrite an existing output. It needs the complete bundle, including the retained `source/` tree and inputs. Post-run addition of unavailable reason codes changed no scientific values and used zero additional fits or replays.

The reviewed aggregate is [strategy-comparison.v 1.json](../../site/src/data/strategy-comparison.v1.json), governed by [the public schema](../../schemas/research/strategy-comparison-public.v1.schema.json) and its exact reviewed canonical hash. Both languages and all chart filters consume the same facts. Raw prices, individual predictions and private paths stay outside public Git. See [workflow checks](../operations/workflow-check.md) for receipt integrity and [manual observation](observation-registry.md) for the separate future-data gate.
