# Research models and timing

The retained large-panel studies contain 16 model blocks on exposed history. They are retrospective diagnostics; all six [scientific evidence requirements](datasets.md) remain blocked. No execution targets or scientific acceptance follow from these runs.

| Model | Frozen candidates and parameters | Current evidence |
| --- | --- | --- |
| Ridge | alpha 0.1, 1, 10 | Retained large-panel retrospective study |
| Elastic Net | alpha 0.0001, 0.001, 0.01 × l1_ratio 0.1, 0.5, 0.9; max_iter 2000; tol 1e-4; cyclic selection | Retained large-panel retrospective study |
| HistGradientBoosting | depth 2, 3; iterations 100; learning rate .05; leaf nodes 7; minimum samples 100; L2 1; bins 63; seed 42; early stopping false | Selected depth 3 in May and 2 in July for both horizons |
| Random Forest / Extra Trees | 100 trees; depth 3, 5; minimum leaf 100; max_features 1; squared_error; seed 42; 2 jobs; RF bootstrap true, ET false | Planned new study; no run claimed here; at most 24 new fit starts |
| Chart CNN | Separate fixed ten-stock exploratory pool, 2 filters and 2 epochs | Separate experiment; cannot be compared directly with the broad panel |

The numerical walk-forward study uses 400 training sessions, 80 validation sessions, a five-session label and five-session purge. This is a separate protocol from the retained low-turnover tree extension, which uses validation60 and at least 80 earlier inner calendar sessions. No Torch dependency is introduced.

Monthly candidate updates select at most 500 candidates using only earlier information. Features update daily. Training occurs at window boundaries, with hyperparameter selection on the earlier validation interval. Portfolios rebalance every 5 or 20 sessions; these are separate clocks. Top50 equal weights with buffer20 retain incumbents within Top70. Buffer0 applies no retention buffer. One-way fees are 0/20/40 bps and execution delays are 0/1 session. The exposed windows are 2026-05-28–2026-07-24 and 2026-07-27–2026-09-21. Six features are session return, range fraction, relative dollar volume, median spread, quote fraction and active fraction. Raw-price cash accounting does not establish total returns.

The frozen future INTENT requires the first XNYS session opening after freeze and no earlier than 2026-11-02, 120 evaluation sessions and another 20 sessions for labels. A supplied calendar remains unverified. Owner/PIT/availability/governance evidence is missing; import and training are disabled, future authorized fits and accepted observations are both zero. Existing observation protocols are unchanged.

The reversal risk-filter design is preregistered separately: use the prior 20-session broad-universe equal-weight raw return; disable new reversal exposure when that return is below -5%, otherwise permit it. Fix this threshold before inspection; compare with a control scaled to the same daily gross exposure, the unfiltered reversal and cash under identical fees/delays. Missing identities/actions/availability block evaluation. It has not been trained or evaluated; the 24-fit authorization covers RF/ET only.

The optional external engine assessment is pinned to `7bd254d3e4e86d72f3edbec09fa4749394e7453e`. Its integer quantities, L1 marks/rounding and absent corporate actions differ from normalized USD1 fractional-share research. A separate CLI synthetic comparison is planned for cash, buys/sells, fees and rounding. Rust is unavailable locally; no binary conformance result is claimed and no default backend changes.

Generate private governance artifacts with `python -m competition_tools.research_governance worklist --output <new-private-file>` or `execution-template`. `future-intent` additionally requires `--calendar <XNYS-json>` and `--bindings <source-and-lock-hashes-json>`. Outputs are exclusive and forbidden inside source checkouts. Hashes bind bytes, not trusted issuers. Actual cost intake requires venue/product/currency/effective dates, fee schedules, timestamped bid/ask spread samples, depth/participation capacity and authenticated receipts. Supervised Paper evidence requires account authorization, qualification, submission, cancellation, fills, restart recovery, reconciliation and kill-switch audit. No credentials, broker calls, orders, scheduler or live configuration are involved.
