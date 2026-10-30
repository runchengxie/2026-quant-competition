# Incremental low-turnover tree study

[简体中文](low-turnover-tree-study.zh-CN.md)

The retained study completed on 2026-10-31. Shallow histogram gradient boosting and a causal 20-session momentum baseline do not establish a stable improvement over simple reversal; no strategy was promoted. Independent verification checked the complete parent run and its exported holding evidence before reusing 168 saved simulated-account configurations. The 96 new simulated-account configurations used 12 fit starts: 60 completed and 36 were blocked, split equally between unusable ranking pools and known corporate-action boundaries.

The two windows, 2026-05-28–2026-07-24 and 2026-07-27–2026-09-21, have already been exposed. Results remain exploratory retrospective comparisons. All six scientific evidence requirements remain blocked. This workflow does not establish total returns, complete historical stock acceptance, availability, liquidity, capacity or tradability, and it creates no execution targets. See the [retained comparison](strategy-comparison.md) and [approved design](../superpowers/specs/2026-10-31-low-turnover-tree-study-design.md).

## Frozen comparison

Each horizon/window block retains the parent's monthly candidate pool, six features, validation60 split, strict label purging, raw-price labels and actual-unit cash ledger. Training needs 80 earlier inner calendar sessions. Imputation fits training rows only. Candidate depths 2 and 3 use the existing `fit_incremental` estimator, with 100 iterations, learning rate 0.05, seven leaves, minimum 100 samples per leaf, L2 1.0, 63 bins, seed 42 and disabled early stopping. Selection uses mean daily RankIC, MSE and declared order, requiring 30 valid candidates/date and 20 valid validation dates. Only the selected candidate receives one outer refit.

Momentum is `close(t) / close(t-20) - 1` at the parent's close-time decision proxy. All 21 exact calendar marks must exist, have valid prices, retain the same candidate and ticker, and contain no known action boundary. No future outcome is used to filter predictions. A missing lookback remains unavailable and can block its account. The proxy itself does not certify historical data availability.

Top50, buffers 0/20, horizons 5/20, single-sided modeled fees 0/20/40 bps and delays 0/1 remain fixed. Each window starts its own account. No NAV is stitched across windows. Missing parent bindings stop the workflow; they never trigger old trial refits. Parent files and consumed reservations remain untouched.

The private protocol predetermines 432 cellwise return comparisons for Ridge, Elastic Net and shallow tree against equal weight, reversal and momentum, with matching window/horizon/fee/delay/buffer. Equal weight always uses its single buffer-0 reference. There are also 24 paired daily RankIC summaries against reversal and momentum, using only matching candidate counts and valid paired dates. Equal-weight RankIC is unavailable because its scores are constant. Missing pairs remain explicit. These conditions share history and overlapping labels; they are not independent observations. Uncertainty stays unavailable with reason `uncertainty_tooling_not_validated`; no confidence intervals or significance claims are added after seeing results.

## Prepare, reserve, run and verify

Complete or explicitly defer the [data-root migration](../operations/data-root-migration.md) and obtain the migration owner's explicit real-run authorization first. Use the selected canonical project root after migration. Do not create canonical outputs while migration is in progress. The protocol binds the full parent record, prepared input bytes, parent exports, current root and leaf source hashes, both lock files, fixed rules and a new owner-scoped output.

Use independently installed root and leaf environments from this reviewed source revision. Root dependencies remain stdlib-only; the leaf uses the existing locked `predictive` extra. Resolve `DATA_ROOT` from the machine's explicit workspace configuration or environment. The following PowerShell commands assume that resolved `$dataRoot` and the installed `$rootPython` and `$leafPython` paths are supplied.

```powershell
$source = (git rev-parse --show-toplevel).Trim()
$project = & $rootPython -c "import sys; from competition_tools.project_storage import project_root; print(project_root(sys.argv[1]))" $dataRoot
$parent = Join-Path $project 'task-results/evidence-followup-20261025/historical-run'
$owner = Join-Path $project 'research/equity-lab'
$output = Join-Path $owner 'tree-study/20261031-v1'
$prepared = & $rootPython -m competition_tools.evaluation.tree_study prepare `
  --owner $owner --parent-run $parent --parent-equity (Join-Path $parent 'equity') `
  --input (Join-Path $parent 'inputs/daily.parquet') --output $output --source-root $source |
  ConvertFrom-Json
& $rootPython -m competition_tools.evaluation.tree_study run `
  --protocol $prepared.protocol --reservation $prepared.reservation --python $leafPython
& $rootPython -m competition_tools.evaluation.tree_study verify --protocol $prepared.protocol
```

Preparation performs the complete parent verification before reserving. It freezes `competition.low_turnover_tree_protocol.v1` and creates a `competition.research_reservation.v1` receipt keyed by protocol and input hash. A different source, output or timestamp cannot restore the same budget. A failed preparation after reservation remains reserved and requires investigation; never delete its receipt to retry.

The selector uses the canonical root after migration, or the legacy-only root when migration is explicitly deferred. A recorded later move resolves known locations without rewriting the immutable protocol or parent records.

The leaf's new entry point is `python -m equity_lab.predictive.tree_study_cli --input <prepared> --output <new-output> --reservation <receipt>`. Launch it through the root `run` command so the parent is independently checked immediately before fitting. The once-only started marker is claimed before work. An immutable initial receipt snapshot, per-horizon claims and authoritative attempt ledgers live beside the owner reservation, outside mutable result directories. Hidden workers must match that initial identity, owner and output. Each horizon has a separate worker, a hard 1,200-second deadline, at most six fit starts, two compute threads and its own report. Failed or interrupted starts consume budget. No automatic retry or resume exists. The importable runner's default real estimator also requires a validated durable horizon claim. Explicit fitter injection is for synthetic tests; these contracts do not sandbox arbitrary Python or scikit-learn execution.

The new leaf report is `equity.low_turnover_tree.v1`. New prediction CSVs include every test candidate/date, even when outcomes are missing. Validation prediction CSVs allow the root to recompute candidate RankIC/MSE and selected depth independently. Root verification checks the exact prediction grids, causal momentum, selection plans, all gross/net account paths, coverage and paired summaries. Blocked accounts retain their reason, date and partial history. Horizon failures retain their started markers, partial reports, timeout records and unavailable cells; a partial run cannot pass completed-output verification.

Keep protocols, reservations, attempts, source/lock identities, parent records, reports and verification evidence under private retention. Synthetic checks use a separately assigned rehearsal namespace during migration. They do not authorize another real fit. Raw prices, candidate predictions and private paths remain private. An unexposed evaluation needs its own future protocol and availability evidence.

## Reproduce the public projection

The existing US strategy and factor pages show a separately reviewed [public aggregate](../../site/src/data/tree-study.v1.json), leaving every earlier snapshot unchanged. Its [closed schema](../../schemas/research/public-tree-study.v1.schema.json) permits only bounded provenance hashes, fixed rules, counts, eight new model summaries and 432 matched return comparisons. Each comparison includes both net returns and their difference; one blocked side leaves the difference unavailable. Equal weight always uses buffer zero. The [publication validator](../../src/competition_tools/evaluation/tree_study_publication.py) pins the reviewed canonical SHA-256 and checks the complete grids, repeated accounts and return relationships.

To recheck saved private results and produce a new private candidate without fitting or acquiring anything, supply the existing protocol and an unused output path:

```powershell
& $rootPython -m competition_tools.evaluation.tree_study_projection `
  --protocol $prepared.protocol --output $privateCandidate
```

The command independently verifies saved outputs with their original source binding, extracts an explicit derived-field allowlist and refuses to overwrite a candidate. It prints the canonical hash. Review that candidate before copying it into public Git; the hash is a publication integrity check, not proof of scientific validity. Both windows were exposed and uncertainty remains unavailable. The six [scientific requirements](datasets.md) remain blocked, including owner provenance and holdout governance; local byte bindings alone do not satisfy them.
