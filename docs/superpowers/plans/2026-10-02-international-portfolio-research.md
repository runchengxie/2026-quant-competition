# International Portfolio Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a reproducible local research path for ETF, individual-equity, and futures sleeves, with point-in-time factor validation and a common cost-aware comparison boundary.

**Architecture:** Keep instrument-specific inputs and sizing inside independent sleeves, then normalize their timestamped return/exposure outputs for comparison. Add a provider-neutral factor observation contract; QuantZone is an optional A-share source behind data-quality and entitlement gates. For non-A markets, factor definitions may inspire locally reconstructed features, but provider values and A-share cutoffs do not transfer.

**Tech Stack:** Python 3.12, existing `src/strategies` package layout, pytest, Ruff; no new mandatory dependencies or GitHub Actions usage.

**Spec:** `docs/superpowers/specs/2026-10-01-international-portfolio-research-design.md`

## Global Constraints

- Use local runs while GitHub Actions quota is unavailable; never place provider or broker credentials in tests, artifacts, Git, Pages, or CI.
- IBKR Paper is the only execution environment; this plan adds no live order path and submits no orders.
- Do not add the QuantZone SDK or authenticated requests until market coverage, point-in-time/revision semantics, quotas, price, and research/publication rights are confirmed.
- AIVIX/Cryptoracle is limited to the declared digital-asset sleeve; missing or stale observations disable only that overlay.
- Futures outputs must retain contract month, multiplier, tick size, currency, expiry, and roll identity; never represent them as an equity ticker/weight alone.
- Publish no raw licensed responses, credentials, account identifiers, holdings, orders, or unverified returns.

## Review Focus

- Provider revisions or late publication could leak future information; test availability cutoffs against observation and retrieval timestamps.
- Duplicate or conflicting factor rows could silently alter ranks; test deterministic rejection and source-version identity.
- A factor catalogue entry may lack formula or rights metadata; test that incomplete records remain ineligible rather than receiving a default.
- Futures roll gaps and contract multipliers can distort portfolio returns; test contract-boundary accounting and missing metadata rejection.
- Different market calendars and currencies can create mismatched comparison dates; test explicit date alignment and FX absence behavior.

---

## File Map

- Create `src/strategies/international_lite/factors.py` for provider-neutral factor metadata, observations, and point-in-time eligibility checks.
- Extend `src/strategies/international_lite/data_quality.py` only with shared validation helpers if needed; keep existing bar continuity behavior stable.
- Create `tests/strategies/test_factor_observations.py` for factor contract and leakage checks.
- Create `tests/strategies/test_factor_catalog.py` for eligibility and missing metadata checks.
- Modify `docs/operations/market-data-inventory.md` to include a clearly labeled QuantZone candidate status only after entitlement evidence is recorded; do not state coverage that has not been tested.
- Modify `docs/strategy/international-lite.md` to describe sleeve boundaries and known proxy limitations.
- Future sleeve-specific work remains split into subsequent executable chunks: ETF accounting/cost model, point-in-time equity universe, and futures contract/roll model.

## Implementation Tasks

### Task 1: Define point-in-time factor records

**Files:**
- Create: `src/strategies/international_lite/factors.py`
- Test: `tests/strategies/test_factor_observations.py`

**Interfaces:**
- Produces `FactorDefinition` with `provider`, `factor_id`, `name`, `formula_version`, `asset_scope`, `market_scope`, `license_status`, and `validated_markets` fields. `market_scope` is a comma-separated set of market codes; `validated_markets` is a tuple of market codes whose reconstruction/validation has passed.
- Produces `FactorObservation` with `provider`, `symbol`, `factor_id`, `period_end`, `available_at`, `retrieved_at`, `value`, and `source_version` fields.
- Produces `eligible_observation(observation, *, decision_cutoff) -> bool`.
- Produces `ensure_unique_observations(observations) -> None`, raising `ValueError` for duplicate provider/factor/symbol/period/version keys.

- [x] Add tests that accept an observation only when `available_at <= decision_cutoff` and reject observations published after the cutoff, with missing or naive timestamps, or with non-finite values; test duplicate keys with equal and conflicting values.
- [x] Run `uv run --locked pytest tests/strategies/test_factor_observations.py -q --basetemp .pytest-tmp` and confirm the new tests fail because the contract is not implemented.
- [x] Implement immutable dataclasses and strict ISO-8601 datetime parsing; require timezone-aware timestamps and preserve source versions.
- [x] Add duplicate-key validation for `(provider, factor_id, symbol, period_end, source_version)` and reject duplicate rows.
- [x] Run `uv run --locked pytest tests/strategies/test_factor_observations.py -q --basetemp .pytest-tmp` and confirm all tests pass.

### Task 2: Gate factor catalogue eligibility

**Files:**
- Modify: `src/strategies/international_lite/factors.py`
- Test: `tests/strategies/test_factor_catalog.py`

**Interfaces:**
- Produces `factor_eligibility(definition, *, market, purpose) -> tuple[bool, tuple[str, ...]]`.
- Eligible purpose values are `research` and `public_summary`; unknown values fail closed.

- [x] Test that QuantZone-like definitions without formula version, market scope, or confirmed license status are ineligible and return stable reason codes.
- [x] Test that A-share scope is not eligible for a US/JP/HK market, while an explicitly scoped cross-market definition still requires the requested market to appear in `validated_markets`.
- [x] Run `uv run --locked pytest tests/strategies/test_factor_catalog.py -q --basetemp .pytest-tmp` and confirm failure before implementation.
- [x] Implement fail-closed checks; research requires `confirmed_research` or `confirmed_research_and_publication`, while public summaries require `confirmed_research_and_publication`. Do not infer rights from a package license or free-tier availability.
- [x] Run both new factor test files; full suite pending final verification.

### Task 3: Document QuantZone validation protocol

**Files:**
- Modify: `docs/operations/market-data-inventory.md`
- Modify: `docs/strategy/international-lite.md`

- [x] Add QuantZone as `candidate / not yet validated`; list required evidence: market/universe coverage, factor ID and formula/version, historical depth, first-available/as-of and revision behavior, survivorship/adjustment treatment, quota/pricing, and use/publication rights.
- [x] State that non-A-market research may use factor names/definitions as hypotheses only and must rebuild from that market's native data.
- [x] Do not add API keys, sample licensed payloads, or claims of coverage to the docs.
- [x] Run the Pages content checker and scan the changed documentation for credentials or local paths.

### Task 4: Verify the local research boundary

**Files:**
- No additional files unless a concrete validation defect is found.

- [x] Run `uv run --locked ruff check src/strategies/international_lite tests/strategies`.
- [x] Run `uv run --locked pytest -q --basetemp .pytest-tmp` and `uv run --locked python -m compileall -q src`.
- [x] Run the repository's Pages content checker and inspect `git diff --check`.
- [ ] Record any failed gate and fix the underlying issue before continuing; do not use GitHub Actions.

### Task 5: Implement independent instrument sleeves in follow-on chunks

**Files:**
- Extend existing `src/strategies/global_etf_rotation/` for ETF total-return/currency/cost assumptions.
- Create a point-in-time equity sleeve under `src/strategies/international_equities/` only after universe and delisting data are identified.
- Create futures instrument/accounting code under `src/strategies/international_futures/` only after contract metadata and roll source manifests are available.

- [ ] For each asset sleeve, first lock its data manifest, timestamp and calendar rules, cost assumptions, and one meaningful test before implementing a signal.
- [ ] Compare all sleeves only on explicitly aligned decision timestamps and common reporting currency; report missing dates and shorter-history limits.
- [ ] Add futures target schema v2 only in a separately reviewed change with v1 readers preserved and round-trip compatibility tests.

## Self-Review

- Spec coverage: factor provenance and QuantZone conditions are covered in Tasks 1–3; local safety and verification in Task 4; ETF/equity/futures sleeves and target v2 are explicit follow-on work in Task 5. AIVIX, Index One, and supervised IBKR Paper gates remain covered by the design spec and are not enabled by this initial factor-contract increment.
- Step clarity: each first four tasks names exact files, interface/behavior, and local commands. Task 5 is deliberately a gated follow-on because the repo does not yet contain validated PIT equity/futures manifests; it forbids fabricating those inputs.
- Type consistency: `FactorDefinition` supplies catalog scope/licensing metadata; `FactorObservation` supplies timestamped values; eligibility consumes the definition and explicit market/purpose; point-in-time eligibility consumes the observation and cutoff.
- Review Focus coverage: timestamp leakage and duplicate conflicts are tested in Task 1; incomplete and cross-market definitions in Task 2; futures metadata and cross-market alignment are explicit gates in Task 5 before the respective implementation.
- Proportion: the initial executable scope establishes a small shared contract and licensed-source gate. It does not attempt to implement three separate backtest engines without validated input manifests.

## Execution status — 2026-10-02

- Tasks 1–4 completed locally; the factor contract, fail-closed catalog checks, QuantZone validation docs, and local verification passed.
- Task 5 remains a follow-on: no validated point-in-time A-share, international equity, or futures manifests have been added, and no three-sleeve backtest or target schema v2 is claimed complete.
- The initial baseline and final local suite pass with `uv run --locked pytest -q --basetemp .pytest-tmp` (123 baseline tests; 141 final tests). Ruff, compileall, Pages content check, and `git diff --check` pass.
