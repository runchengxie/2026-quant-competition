# Equity prediction study

Ridge showed little ranking effect in the middle test period and a larger positive effect in the last. Three periods do not establish a dependable trading advantage. Formal trading performance remains unavailable.

## What was measured

The source covers 2025-09-25 through 2026-10-20. It contains 2,516 source codes and 2,518 candidate identity segments, including 2,511 unresolved segments. These are source candidates, with incomplete historical type and identity evidence. They are not a certified common-stock universe or historical index membership list.

At each month boundary, eligibility uses the previous 20 complete XNYS sessions, excluding the new month. All 20 dollar-volume observations must exist. The prior close must be at least USD5 and mean dollar volume at least USD10 million. Rank by this mean, break ties by candidate ID, cap at500 and freeze for the month. No future first-day observation is required. Each eligible month from November2025 through October2026 contained500 candidates. The initial partial months have insufficient history.

The label is the next exchange session's last usable regular-session trade divided by its first usable trade, minus1. A missing next session stays missing. This is a price-prediction label. Official auction prices, order fills, capacity and total returns have not been established.

Six fixed features describe the completed session. They are first-to-last return, high-low range divided by first price, dollar volume relative to the prior20 sessions, median spread fraction, valid-quote minute fraction and active-trade minute fraction. Minute fractions use the actual session length, including early closes. Missing features are imputed from training data only. Unadjusted overnight returns are excluded.

## Fixed protocol

Python3.12 uses optional locked scikit-learn1.7.2, pyarrow23.0.1, exchange-calendars4.13.2 and threadpoolctl3.6.0. The default equity engine and CLI are unchanged.

The last60 eligible calendar feature dates define three consecutive20-session test blocks. Earlier dates form expanding training sets with at least126 calendar dates. The last20% of training dates form inner validation. Labels must end strictly before the next decision boundary. All candidates on a date stay together. Scaling and median imputation fit only training rows.

Ridge tests alpha0.1,1,10. Elastic Net tests alpha0.0001,0.001,0.01 crossed with l1_ratio0.1,0.5,0.9, cyclic selection, max_iter2000 and tol1e-4. Select by highest mean daily validation rank IC with at least20 valid dates and30 distinct candidates per date. Ties within1e-12 use lower mean daily squared error, then grid order. There is no error-based fallback when IC coverage is insufficient. Solver nonconvergence is a failed fit. Outer test results never select parameters.

The pilot made42 fit attempts. The hard limits are48 attempts, one worker, at most two BLAS threads and a1200-second subprocess timeout. Attempts are written before fitting; existing output directories are refused. Interrupted and timed-out runs require review before a new run.

## Actual corrected results

Rank IC measures whether higher scores accompany stronger later price moves. It ranges from−1 to1 and carries no currency unit. Means give each valid date equal weight.

| Test dates | Ridge IC | Elastic Net IC | Current-session-return rank IC | Scored candidate-days |
| --- | ---: | ---: | ---: | ---: |
| 2026-07-27 to2026-08-21 | 0.020962 | Undefined | −0.016285 | 10000 |
| 2026-08-24 to2026-09-21 | −0.000037 | 0.000497 | −0.000497 | 10000 |
| 2026-09-22 to2026-10-19 | 0.064979 | 0.064575 | −0.069205 | 9954 |

Each block requested20 dates. Ridge and the current-session baseline have20 valid IC dates in every block. Elastic Net has0,20,20. Its first test block produced a constant forecast, making IC undefined. The always-zero baseline has undefined IC throughout. Missing values remain undefined rather than0. The final block lacks46 candidate-day labels; test dates remain fixed. Distinct identities across a block are539,531,526 because monthly membership changes, while a single date remains capped at500.

Ridge selected alpha10,10,1 across the blocks. Elastic Net selected(alpha0.001,l1_ratio0.5),(0.001,0.5),(0.0001,0.1). In the first block its mean squared error was slightly lower than always predicting0, despite its undefined rank IC. Error and ranking measure different properties.

A first diagnostic run exposed a first-day-observation eligibility condition. A regression test reproduced that lookahead, and eligibility was corrected to use only the previous month. The corrected frozen-input run produced the same reported metrics. The superseded private receipt is retained for audit.

## Reproduce privately

Set absolute DATA_ROOT and an external UV_PROJECT_ENVIRONMENT as described in the team quickstart. Use a completed, frozen daily_features.parquet with the documented columns. Raw data and private receipts stay outside Git.

```powershell
cd research/equity-lab
uv sync --locked --group dev --extra predictive
uv run --locked --extra predictive python -m equity_lab.predictive.cli --input $FROZEN_INPUT --output $NEW_RESULT_DIR --mode exploratory_source_candidates
```

The public equity-predictive.v1.json contains only reviewed per-date aggregate errors, IC values and counts, with source hash and declared limits. The root publication gate independently checks field allowlists, numeric types, calendar boundaries, daily means and coverage, then compares the two localized rendered facts. No raw prices, account information, private paths or individual model predictions are published.

Formal stock PnL requires dated security identity/type evidence, relevant action handling and an execution/cost acceptance check. Historical source selection and survivorship remain unresolved. The bar-close availability timestamp is an unverified proxy. This period had already been explored, so the split is retrospective. The existing forward-observation registry remains unchanged.

## Storage handoff

The source owner's by-security conversion is still running. Its staging output remains untouched. The guarded storage tool refuses incomplete runs, checks the final file_index.csv against row/volume totals and SHA256 receipts, and can explicitly copy only a completed final layout to a new mounted destination. It excludes staging and the path-dependent DuckDB catalog. The original ZIP needs a separate frozen transfer manifest. No copy, source deletion or shared-data pointer change occurred in this milestone.

```powershell
uv run --locked python -m competition_tools.datasets.storage_handoff --source $COMPLETED_LAYOUT --output $NEW_PRIVATE_MANIFEST
```

Run this command at the repository root. Add --copy-to only for an explicitly prepared new dated mounted destination. A failed copy leaves a .partial directory for inspection and refuses an automatic retry. SSH transport and automatic background triggers are outside this tool. Keep source originals until a separate retention decision.

The optional reader was patched from PyArrow21.0.0 to23.0.1 after dependency audit. The actual pilot used21.0.0. Both readers produced the same complete658472-row dataframe fingerprint from the frozen input; no extra parameter search was performed for this change. See the [Apache23.0.1 release record](https://arrow.apache.org/blog/2026/02/16/23.0.1-release/).
