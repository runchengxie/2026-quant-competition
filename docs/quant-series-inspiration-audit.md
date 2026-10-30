# Quant-series inspiration audit

[简体中文](quant-series-inspiration-audit.zh-CN.md) · [Documentation](README.md)

Reviewed on 2026-10-31 against this project's baseline `79e592ad0015f2863377d88a52541e6e3f370639`. Core engineering ideas have been adopted; research methods still need selective completion. This is a capability audit, not a completion percentage or research acceptance.

## Scope and evidence

An authenticated GitHub repository inventory identified 36 owner repositories whose names strictly start with `quant-`, including private and archived repositories. Inventory is not a code audit of all 36. Private inventory and unpublished strategy details stay outside public Git. The detailed decisions below cover relevant capabilities; additional repositories require individual inspection before making implementation claims.

Local source references inspected: `quant-platform` at `28a32ba707ad72d1eb68cde5075663e1b3819ac7`, `quant-market-data-platform` at `24973c0099bf2c5324ba956027c9fa67dc698100`, and the research owner's experiment/evidence interfaces. These local revisions are not asserted to be current remote main. The [Alpha 810 contract](https://github.com/runchengxie/quant-factor-observatory/blob/c49a44353130851d71a3c7c7605a108a302c40e3/docs/alpha810-public-contract.zh-CN.md) was read through GitHub at the pinned revision. No private implementation is reproduced here. Earlier validation counts in linked documents remain dated historical evidence; this audit does not rerun those experiments.

## Capability decisions

| Source and capability | Applicable use and current evidence | Decision and target | Verification / closure condition |
| --- | --- | --- | --- |
| quant-platform: accounting and causal clocks | Local `research/platform-compare`; [accounting comparison](research/accounting-comparison.md) records extraction, licensing and historical parity checks | Adopted for software diagnostics; retain independent package | Real-input admission remains separate; synthetic compatibility does not certify provenance |
| quant-platform: portfolio policy separation | `equity_lab/portfolio`, `crypto_mm/portfolio`, `check_workflow_boundaries.py` | Adopted; preserve model-specific semantics | Existing boundary checker and compatibility tests guard regressions |
| quant-platform: HRP and probability sizing | [AFML methods](https://github.com/runchengxie/quant-platform/blob/28a32ba707ad72d1eb68cde5075663e1b3819ac7/docs/concepts/afml-sizing-and-risk.md); current project already has weight limits and volatility controls | Defer until a defined portfolio needs covariance budgets or independently calibrated probabilities | Compare with existing equal-weight/volatility controls on frozen inputs; assess weight stability, turnover and net performance |
| Data-owner projects: identity, historical universe, actions and availability | `competition_tools/datasets`, `research_acceptance.py`; current receipts do not independently authenticate all owner facts | P0 open; establish an owner-specific evidence adapter before changing acceptance | Bind immutable owner asset/version, security identity intervals, membership, actions, price basis and availability to consumed bytes; fail missing/conflicting evidence |
| Research-owner workflow: experiment records and holdout governance | `evaluation/run_record.py`, reservation and observation registries, `experiment_acceptance.py` | Engineering adopted; research promotion blocked | Independent owner protocol validation must bind candidate, frozen source/config, allowed sample and exposure history |
| quant-factor-observatory: daily factor diagnostics | `equity_lab/evaluation/signals.py` has daily IC with pooled fallback; crypto factor publication already contains grouped returns | P1 open for a strict equity diagnostic API; preserve legacy demo API | Daily IC/RankIC with valid-date counts, deterministic quantiles/ties, missing-data policy and horizon decay; never pool dates as an implicit fallback |
| quant-factor-observatory: statistical uncertainty | Pinned Alpha 810 contract specifies Bartlett/Newey–West, circular block bootstrap and BY/BH families | P1 adopt methods selectively in `equity_lab/evaluation`; implementation pending | Freeze horizon, lag grid, block length, seed, draws and entire test family; retain invalid tests; validate numerical references and serial-dependence fixtures |
| quant-market-research: executable costs and capacity | Existing cost sensitivity, turnover, holding controls and robustness producers | P1 open; extend existing input/evidence contracts | Source fee schedules, spread, impact/participation and capacity assumptions with dates and units; distinguish modeled costs from observed execution |
| quant-deep-learning: model validation | Existing predictive/CNN studies and frozen study records | Adopt validation discipline; no model migration required | Predetermine temporal splits, label-overlap purge, seed set and net-value controls; retain failed/constant forecasts and all attempted trials |
| Execution contracts and Paper lifecycle | `schemas`, preflight, audit and reconciliation; published v1 schema JP/US differs from runtime HK recognition | P1 open, separately scoped execution task | Reconcile schema/runtime examples and tests; supervised Paper submission/cancel/fill/restart/reconciliation evidence remains required |
| quant-backtest-runtime: durable jobs | Independent installed CLI workflows already exist; runtime requires Linux | Defer; no current requirement for a distributed scheduler | Revisit when durable queues, restart recovery or concurrent compute demand exceeds local orchestration |
| quant-intel delivery, deployment and briefing | Reviewed research publication already has a local owner | Exclude production delivery migration from current scope | Revisit for an explicit consumer, audience or scheduler requirement |
| Course, final-project and archived repositories | Inventory alone does not establish applicable validated methods; no current credit/options mandate | Exclude wholesale migration; inspect individual methods only when a matching study is proposed | Record the new use case and provenance before adopting code or claims |

The Alpha 810 example uses lags 0/1/5/20/60, circular 20-session blocks and 2,000 draws on its own historical panel. These are source choices, not approved defaults for this project. Its grouped returns are single-period descriptive labels without execution costs. Uncertainty estimates and multiple-testing correction cannot restore unseen test data.

## Ordered next work

Initial P0 receipt triage on 2026-10-31 inspected the retained US/HK fixed-daily v2 receipts and the Databento daily pilot. Both fixed-daily receipts report acquisition complete but `accepted_research=false`; corporate actions and revisions outside the overlap interval remain unverified. The pilot reports partial acquisition, `LISTING_CALENDAR_UNVERIFIED`, and unverified historical availability. These are receipt declarations, not independent owner certification. Receipt hashes and private locations are retained in the task inventory; referenced market-data bytes were not revalidated. An empty acquisition issue list is therefore insufficient for research acceptance.

1. **P0 evidence inventory.** Select one explicit dataset and candidate, list required owner records, record present/missing/contradictory evidence, and freeze references. Do not acquire paid data or reuse consumed research reservations under this task.
2. **P0 adapter design and implementation.** Specify the trusted owner identity and protocol, versioned receipt schema, artifact/hash binding, availability and universe/action semantics, and negative fixtures. Implement against that selected owner only after the design is settled. Generic caller flags and self-supplied hashes cannot authenticate an owner.
3. **P0 promotion review.** Independently validate the holdout protocol and its exposure history. Preserve `OWNER_CONTRACT_VALIDATION_UNAVAILABLE` until the actual supported path can prove both provenance and governance. Unsupported owners stay blocked; never remove the blocker globally.
4. **P1 strict factor diagnostics.** Add a pure evaluation module with frozen statistical choices and reference tests. Keep historical/demo metrics unchanged, and label reused history retrospective.
5. **P1 execution/cost evidence.** Resolve target consistency in its own reviewed change, then collect authorized cost/liquidity evidence and supervised Paper lifecycle records. Research tooling must not initiate broker operations.

The first P0 implementation needs a named owner dataset and verifiable owner/holdout records. Their existence has not been established by this audit. Completing this document closes the audit deliverable only.

## Completion rules

The first P0 implementation is the [daily evidence-gap inventory](research/datasets.md#audit-retained-daily-research-evidence). It reuses complete payload verification for IBKR daily v2 and creates a blocked-only report. This closes reproducible inventory tooling, not owner authentication, PIT coverage or research promotion. The initial triage above remains a dated historical record.

Each capability closes with a pinned source, explicit applicability decision, target implementation, actual validation record and remaining limitations. “Deferred” and “excluded” are valid decisions with a reason and revisit trigger. Engineering closure, scientific acceptance, and broker readiness remain separate. Update this table when new evidence changes a decision; do not mark open evidence gaps complete because CI passes.
