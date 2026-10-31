# Saved-score retrospective diagnostics

This opt-in workflow creates a **new private post-hoc report on exposed history**. It does not change the retained tree study, its reviewed public snapshot, its unavailable uncertainty, or any scientific acceptance gate. No fitting, acquisition, replay, broker access, target export or promotion is authorized. External owner, point-in-time, quote and Paper evidence remain blocked.

The calculation family contains the 16 saved model blocks (Ridge, Elastic Net, shallow tree and momentum20, each at two training horizons and two exposed windows), crossed with fixed-score forward labels of 1/5/10/20 sessions. Each block retains its own complete 40-session grid. Windows and NAV series are never concatenated.

Quintile edges use linear 20/40/60/80 percentiles of all finite decision-cohort scores, before observing label availability. Equal scores go to the first upper edge greater than or equal to the score. Fewer than five distinct scores or repeated edges makes quintiles unavailable. Daily rows retain cohort size, finite score count, valid-label coverage, bucket counts, raw forward-return means and descriptive top-minus-bottom returns. These returns are not investable portfolio PnL and are outside the testing family. Daily RankIC requires 30 usable candidates and nonconstant scores and labels; a missing prediction with a usable label makes that daily IC unavailable.

Labels run from the next session's raw open to the horizon's raw close. Observations inside that future pricing interval must have valid positive prices, one nonempty ticker identity, and no known action boundary. Decision-day OHLC or an already completed action lies outside that pricing interval and does not invalidate its return. Missing calendar observations or label tails remain unavailable. Before any report statistics, independently reconstructed strict 5/20 labels must match every bound original 5/20 label, including unavailable cells; a discrepancy stops the new report instead of silently changing the sample.

The inferential observation is one cross-sectional RankIC per session. The estimand is its equally weighted daily mean. Inference requires a complete contiguous calendar slice and all three conditions: n≥30, n≥4h, and n≥4max(5,h). Missing, nonfinite or constant daily ICs keep an explicit reason. Thus 20-session inference is unavailable for these 40-session blocks. Descriptive means may use available daily ICs, with their valid-session count reported separately; inference never drops missing sessions.

Bartlett Newey-West uses lag h−1 and the n/(n−1) finite-sample correction. Normal diagnostic 95% intervals use z=1.959963984540054; two-sided p=erfc(|mean|/SE/√2). The non-circular moving-block bootstrap uses length max(5,h), 2,000 draws and Python `random.Random(20261031)`, reset for each hypothesis. Each draw takes ceil(n/length) uniformly sampled block starts from 0 through n−length, concatenates, truncates to n and averages. Bootstrap percentile endpoints use linear interpolation. There is no bootstrap p-value. Holm correction includes all 64 hypotheses; unavailable values internally pad with p=1 and retain unavailable output. This correction does not cover the project's adaptive search or establish independent discovery, causality or future performance.

## Freeze, run and verify

Use a reviewed, committed, clean source checkout and separately installed root/leaf environments. The root CLI is stdlib-only; it communicates with the equity leaf through files and a separate Python process. The leaf uses existing NumPy/pandas dependencies. Keep all outputs beneath the canonical external `DATA_ROOT/global-market-research`, with new exclusive owner/output paths. Do not use an existing retention folder itself as the new owner.

```powershell
& $rootPython -m competition_tools.evaluation.posthoc_diagnostics prepare `
  --parent-protocol $retainedTreeProtocol --owner $newPrivateOwner `
  --output $newPrivateResult --source $reviewedSource
& $rootPython -m competition_tools.evaluation.posthoc_diagnostics run `
  --protocol "$newPrivateOwner/protocol.json" --python $leafPython
& $rootPython -m competition_tools.evaluation.posthoc_diagnostics verify `
  --protocol "$newPrivateOwner/protocol.json"
```

In PowerShell, prefix executable variables with `&`. Prepare fully verifies the original retained tree and parent exports, reads their CSVs without a parquet dependency, freezes complete file inventories, raw-input hash, original public semantic/byte hashes, source identity, locks, normalized evidence and the complete ordered 64-hypothesis family. It writes `inputs.json` and `protocol.json`, and does not calculate new uncertainty. Run rechecks bindings before and after the child. Durable exclusive root and producer claims precede calculations; failures retain partial output and cannot retry in that output directory. Verification independently reconstructs inputs from the verified saved exports, recomputes every diagnostic with stdlib arithmetic and rejects changed/extra fields or files. Existing verification receipts must also match. Review/source freeze precede the first real historical calculation; synthetic completion alone does not authorize scientific promotion.

Closed v1 schemas are in `schemas/research/posthoc-{inputs,diagnostics,diagnostics-protocol}.v1.schema.json`. Synthetic end-to-end checks require explicitly setting `POSTHOC_LEAF_PYTHON` to the separately installed equity Python; default root tests remain independent of leaf imports. The implementation tests cover hand-computed HAC, fixed block resamples, ties/label masking, missing values, strict identities/actions, complete-family correction, file tampering and exclusive attempts. No actual new historical result is included in this change.
