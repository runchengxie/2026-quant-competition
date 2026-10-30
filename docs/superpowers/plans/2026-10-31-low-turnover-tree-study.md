# Low-turnover tree study implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reserved, opt-in retrospective tree and momentum comparison that reuses verified parent accounts.

**Architecture:** A stdlib root orchestrator freezes and verifies parent bindings before invoking an independently installed leaf CLI. The leaf preserves the original training slices and accounting and writes a new report version. Immutable owner-scoped initial/horizon claims and attempt ledgers prevent output-directory resets. The root checks new selections, predictions, cash paths and owner ledgers independently.

**Tech Stack:** Python 3.12; existing pandas, NumPy and scikit-learn in the leaf only; root stdlib only.

**Spec:** `docs/superpowers/specs/2026-10-31-low-turnover-tree-study-design.md`

## Global constraints

- No real fits before the migration owner explicitly authorizes them.
- Two horizons, two exposed 40-session windows; validation60 and 80 prior inner calendar sessions.
- Depths 2/3, at most one selected refit per block; at most six attempts and 1,200 seconds per horizon, two threads.
- Exactly 168 verified parent requested accounts reused; at most 96 new requested accounts; no old trial refits.
- Top50, buffers 0/20, fees 0/20/40, delays 0/1; existing raw-price actual-unit accounting.
- Preserve old modules and acceptance rules. New versions only; six scientific gaps remain blocked.

## Review focus

- Missing or altered parent input, plan, prediction or account must fail before fitting.
- Momentum must reject calendar gaps, action boundaries and identity/ticker changes and ignore future observations.
- An interrupted reserved start consumes the run; hidden/default API paths require owner claims, and attempt records precede fit calls.
- Constant predictions and incomplete grids must preserve unavailable/blocked results.
- Tampered saved prediction, plan, account or paired summary must fail root verification.

### Task 1: leaf causal scoring and bounded runner

**Files:** Create `research/equity-lab/src/equity_lab/predictive/tree_study.py`, `tree_study_cli.py`, `tree_study_guard.py` and `research/equity-lab/tests/test_tree_study.py`.

**Interfaces:** `momentum_scores(base, sessions)` returns causal scores; `run_tree_study(raw, schedule, output, binding)` writes new-only artifacts; CLI consumes the frozen protocol and reservation.

- [x] Write failing momentum, attempt-budget, selection and full blocked workflow tests.
- [x] Observe failures, implement the fixed workflow with durable state and strict input/export equality checks.
- [x] Run leaf suite and Ruff in a separate temporary environment.

### Task 2: root protocol, reservation and independent consumer

**Files:** Create `src/competition_tools/evaluation/tree_study.py`, `tree_study_validation.py`, `tests/competition_tools/test_tree_study.py`, `schemas/research/low-turnover-tree.v1.schema.json`.

**Interfaces:** `prepare(...)` verifies complete parent run and holding exports, freezes hashes/source/locks/output and reserves once; `run(...)` preflights then launches the leaf process; `verify(...)` validates new output and pairs matching accounts.

- [x] Write failing parent-binding, reservation-restart, changed-source and tampered-output tests.
- [x] Observe failures, implement stdlib-only verification and bounded subprocess supervision.
- [x] Run root suite, import boundary checks, schema and Ruff checks.

### Task 3: documentation and handoff

**Files:** Create bilingual `docs/research/low-turnover-tree-study.md` and `.zh-CN.md`.

- [x] Document exact prepare/run/verify commands, immutable retained parent records, unavailable uncertainty and blocked scientific claims.
- [x] Review diff; record synthetic verification and prepare the tested implementation commit without pushing, merging or real fits.

## Execution decisions

Native execution was explicitly assigned by the coordinating agent; the design and implementation are approved. Independent whole-branch review follows implementation. Uncertainty remains unavailable (`uncertainty_tooling_not_validated`); paired summaries are cellwise net-return differences and equal-cohort daily RankIC differences with valid-pair counts, never concatenated NAV or confidence intervals.

## Verified implementation record

- Full root suite with existing locked `test` and `daily-data` extras: **1356 passed**, 94 dependency deprecation warnings, 315.03 s.
- Full leaf suite with existing locked `predictive` extra and dev group: **301 passed**, 20 dependency deprecation warnings, 276.70 s.
- Full synthetic integration is included in the leaf suite: 168 saved parent accounts, 96 new accounts, 12 bounded starts, 432 return pairs and 24 RankIC pairs. It independently rejects altered parent/prediction/plan/cash/report/summary evidence, missing validation starts and hidden-worker output rebinding. A synthetic recorded legacy-to-canonical move preserves protocol bytes and passes saved-output verification.
- Root and leaf Ruff passed. Import-direction verification checked 339 source files with zero violations. The root workflow's minimal-environment stdlib tests also passed before installing optional test dependencies.
- Independent review findings were fixed with regression tests: missing ticker parity, durable validation-start proof, strict model metadata, owner-scoped hidden-worker claims, default real-estimator API claims and known-field path relocation. No storage code or old scientific modules changed.
- A final audit-only correction makes failed aggregate counts read the authoritative owner ledger even when an output mirror is interrupted. Its RED-to-GREEN regression and all study unit guards passed afterward: **17 passed, 1 integration deselected**; leaf Ruff passed. Scientific behavior did not change, so unrelated full suites were not repeated for this count-source correction.
- The first full root run used an incomplete test environment and had five missing-optional-dependency failures. Installing the existing locked daily-data extra resolved them without product or lock-file changes. The initial mutable-source integration intentionally failed closed; the final integration ran on frozen source.
- No real input was trained, no PR was created, and nothing was pushed or merged by this implementer. Physical data migration is deferred to the coordinating agent; tests wrote only to the explicitly assigned rehearsal namespace. Full logs, JUnit reports, synthetic artifacts and the execution ledger remain private for later canonical retention.
