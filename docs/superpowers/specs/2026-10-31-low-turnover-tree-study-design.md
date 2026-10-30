# Low-turnover stock ranking: nonlinear incremental study

## User choice and research question

The user selected low-turnover stock ranking against reversal, momentum and equal-weight baselines. The project already has Ridge, Elastic Net, shallow histogram gradient boosting and CNN experiments. Existing results do not establish a stable learned advantage over reversal.

Test one new question: does the existing shallow nonlinear model add value for 5/20-session holding periods, when evaluated with the same population, costs and accounting as the retained low-turnover study? This is an exploratory retrospective comparison. The six research-evidence requirements remain unverified.

## Approaches

1. Add a new deep-learning framework or large hyperparameter search. Deferred: it would add dependencies and trial counts before establishing a useful baseline increment.
2. Reuse the retained low-turnover study, add shallow-tree and momentum arms, and preserve the saved linear/baseline outputs. Recommended and consistent with the selected direction.
3. Use ML as a risk filter for an existing strategy. A valid separate question, but the user selected ranking for the first study.

## Inputs and reuse

Use the retained prepared US candidate panel and its calendar, known-action flags, six existing features and monthly source-candidate membership. Freeze exact parent manifests, input hashes, code/lock digests and output references in a private plan before any fit. The ten-name daily cache is a separate fixed-pool diagnostic; it must not replace the existing broader panel merely because it is easy to load.

Retain the two previously studied signal windows, 2026-05-28 through 2026-07-24 and 2026-07-27 through 2026-09-21, with the original session grids and label conventions. Reused history remains exposed. No new dataset acquisition or expansion of the candidate universe is included.

Reuse saved equal-weight, reversal, Ridge and Elastic Net predictions/accounts only after independently verifying their complete parent bundles and matching input, horizon, candidate/date grid, features, validation profile, costs, buffer and execution assumptions. Do not refit consumed studies or fill unavailable cells with hindsight. If any required parent binding cannot be proven, stop that comparison and report the reason; do not silently rebuild it.

## Frozen candidate and account matrix

- Retain the parent `validation60` split: 60 validation sessions, at least 80 earlier inner-training calendar sessions and strict label-end-before-next-decision boundaries. Keep same-date candidates together. Fit imputation/scaling only on training data. No shuffled split, random early stopping or whole-panel preprocessing.
- Add histogram gradient boosting using the existing `fit_incremental` tree implementation: depths 2 and 3, 100 iterations, learning rate 0.05, seven leaves, minimum 100 samples per leaf, L2 1.0, 63 bins, seed 42 and early stopping disabled. No parameter/seed expansion after observing outcomes.
- Select depth using existing daily RankIC rules (minimum 30 valid candidates/date and 20 valid validation dates), with the existing MSE and declared-order tie breaks. Constant forecasts, invalid labels and insufficient dates remain unavailable. Refit only the selected tree once on the permitted outer-training sample.
- Four horizon/window blocks require at most 12 new fits: two depth candidates and at most one refit per block. Cap each horizon at six attempts, two compute threads and 1,200 seconds. Persist and reserve each attempt before starting the fit; failed or interrupted starts consume it. No automatic retries or hidden budget reset.
- Add a 20-session price-momentum ranking baseline, using only completed, contiguous historical observations available by the existing decision-time convention, never later outcomes. Missing lookback, identity gaps and known action boundaries make that decision unavailable. This proxy does not independently verify historical availability.
- Use original Top-50 selection with buffer 0/20, equal weighting, existing actual-unit cash accounting, horizons 5/20, single-sided modeled fees 0/20/40 bps, and original/one-session-delayed execution. Reuse the parent's 168 requested accounts where bindings match. Tree and momentum add at most 96 requested accounts. Keep each window as an independently initialized account; do not concatenate them into a claimed live or out-of-sample NAV.

## Measurements and limits

Record valid-date counts, daily RankIC/MSE, selections, gross/net modeled returns, turnover, costs, exposure and drawdown. Pair comparisons by window, horizon, cost, delay and buffer; compare each learned arm with equal weight, reversal and momentum where available. Report missing cells and shared-history dependence. More configurations do not create more independent observations.

Predetermine paired summaries and the full trial family in the private protocol. Any Newey–West or block-bootstrap diagnostics must be specified before the real run, preserve within-window time order and overlapping-label dependence, and retain invalid/insufficient samples. Such intervals remain descriptive; they cannot turn these exposed windows into an independent test. If uncertainty tooling is not yet validated, leave uncertainty fields unavailable and state why rather than improvising a statistical claim after seeing results.

Do not claim total-return accuracy, full-market security acceptance, real liquidity/capacity or tradability from this study. Preserve raw-price accounting and the parent's documented exclusions. A better RankIC without useful net comparison is not a promotion criterion. Negative or inconclusive results are acceptable outcomes.

## Delivery and next stage

Implement a new explicit protocol/report version rather than changing legacy or `validation60` behavior. Keep the root consumer stdlib-only and communicate with the independently installed leaf through versioned CLI artifacts. Test synthetic causal splits, momentum lookback, parameter selection, reuse binding failures, budget exhaustion, constant forecasts and all blocked-account paths before real work.

Run the real study only after the data-root migration is settled or explicitly deferred, all parent bindings are verified, and the new owner-scoped reservation binds the approved protocol, source, lock, inputs, budget and new output location. Retain original consumed reservations and attempt markers.

Publish no raw prices, individual predictions, private paths or automatically promoted strategy targets. Any reviewed aggregate needs its own closed schema and publication review. A genuinely unexposed evaluation requires a separately frozen future protocol, access governance and independently evidenced data availability; this study does not supply those records.

Use existing scikit-learn dependencies; no LightGBM/XGBoost/GPU installation is needed. Official guidance on [training-only preprocessing](https://scikit-learn.org/1.7/common_pitfalls.html) and [time-series cross-validation](https://scikit-learn.org/1.7/modules/cross_validation.html#time-series-split) supports these leakage controls; panel-specific label purging remains the project's responsibility.
