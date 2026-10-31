# Bounded retrospective forest study

This is a separate private experiment on already exposed history. It does not
produce execution targets or change scientific acceptance. All six evidence
requirements remain blocked and uncertainty remains unavailable. Previous tree
reports, public results and consumed fit reservations remain unchanged.

The new protocol is `equity.low_turnover_forest.20261031.v1`; the leaf report is
`equity.low_turnover_forest.v1`; the independent root binding is
`competition.low_turnover_forest_protocol.v1`. It first independently verifies
the retained tree protocol and its parent, binding every retained file and the
reviewed public tree hash. For the retained production input it also reproduces
the reviewed public projection before reservation. It reuses all 264 requested
prior accounts and never retrains Ridge, Elastic Net, HGB or momentum.

The fixed models are RandomForestRegressor and ExtraTreesRegressor from
scikit-learn 1.7.2, each at depths 3 and 5. Every constructor parameter is explicit
in the frozen rules. Both use 100 estimators, minimum leaf size 100, all six
features, squared-error criterion, seed 42 and two jobs. Random Forest bootstraps;
Extra Trees does not. Median imputation is fitted only on the corresponding
training slice, retaining empty features. Candidate selection uses validation
mean daily RankIC, then MSE and declared order, requiring 30 candidates per date
and 20 valid dates. The validation period is 60 calendar sessions, after at least
80 earlier inner sessions; both training slices purge labels by their end time.

Each model/window/horizon has two validation starts and at most one refit.
The entire experiment allows 24 starts, at most 12 per horizon. Horizons 5 and
20 run serially, with a 1,200-second hard worker deadline each and two threads.
There are no retries or seed expansion. Owner-scoped exclusive reservations,
initial receipt snapshots, worker tokens, horizon claims and durable attempt
ledgers survive failed or deleted output directories. Supported real defaults
require a validated owner claim. Explicit fitter injection is a synthetic test
seam, not a sandbox for arbitrary owner Python.
The default real root launcher, leaf worker and leaf API additionally require
the exact retained input fingerprint; synthetic prepared protocols cannot start
real fits through those defaults.

The two exposed 40-session windows, causal monthly universe of at most 500,
six features, Top50, buffers 0/20, fees 0/20/40 bps and delays 0/1 match the
previous study. The raw-open actual-unit cash ledger is unchanged. All 96 new
requested accounts are retained, including blocked cases, producing a combined
360-account family. Predictions include the full decision grid even where
future labels are unavailable. Validation predictions, selected parameters,
attempt references, plans and full cash paths are saved. The root stdlib
consumer independently reconstructs selection, chronology, predictions, plans,
cash paths and the fixed 576 paired net returns against equal weight, reversal,
momentum20, Ridge, Elastic Net and HGB. Equal weight always uses buffer zero.

After reviewed integration and explicit coordinator approval to begin the
once-only experiment, use the root environment to freeze and reserve:

```powershell
python -m competition_tools.evaluation.forest_study prepare `
  --owner "$DATA_ROOT/global-market-research" `
  --tree-protocol "$TREE_PROTOCOL" --input "$DAILY_PARQUET" `
  --output "$DATA_ROOT/global-market-research/research/equity-lab/forest-study/20261031-v1" `
  --source-root "$REVIEWED_SOURCE"
python -m competition_tools.evaluation.forest_study run `
  --protocol "$FOREST_PROTOCOL" --reservation "$FOREST_RESERVATION" `
  --python "$PINNED_LEAF_PYTHON"
python -m competition_tools.evaluation.forest_study verify --protocol "$FOREST_PROTOCOL"
```

Retain the printed protocol and reservation paths outside source. The output
must not exist before launch. Source, locks, inputs, parent exports or receipt
changes invalidate the binding. A timeout or interrupted worker conservatively
consumes its starts and retains unavailable cells; it cannot be restarted by
choosing another output directory. Incomplete artifacts cannot pass complete
independent verification. Public presentation requires a separate reviewed
projection; this workflow writes private results only.

Synthetic contract verification uses separate installed root and predictive
leaf environments. Set `GMR_FOREST_ROOT_PYTHON` to the root interpreter and run
`pytest tests/test_forest_study.py tests/test_forest_guard.py tests/test_forest_contract.py`.
Keep test artifacts outside any source repository, including inherited home
repositories. No retained market-data fits are performed by these tests.
