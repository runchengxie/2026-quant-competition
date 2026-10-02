# USD Price Ledger Stage A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver a reusable, causal USD cash-equity/ETF quantity ledger in quant-platform, with synthetic reconciliation tests and official diagnostic artifacts.

**Architecture:** Keep quantities and USD cash between events, value local prices through explicitly selected historical FX pairs, and apply costs only to actual modeled transactions. Reuse `UnifiedLedger` and `write_backtest_bundle` for diagnostic publication. The competition repository retains the approved design and this plan; research callers own signal schedules and released data inputs.

**Tech Stack:** Python 3.12+, standard-library Decimal/datetime/dataclasses, existing pandas, pytest, Ruff and research-contracts. No provider SDK or new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-10-02-usd-portfolio-accounting-design.md` in the competition repository; copy this approved file unchanged alongside this plan into the isolated quant-platform worktree before implementation.

**Implementation repository:** `quant-platform`; inspected baseline `bbe8b51bc5edc34c4c1dee69b9c28999f8da4453`. Recheck interfaces against fetched `origin/main` before starting. Do not change the competition runner or its existing baseline formula in this plan.

## Global Constraints

- Generic mechanisms belong in quant-platform. No providers, credentials, real datasets, competition symbols, strategy parameters or orchestration code enter that repository.
- Inputs contain explicit currency/unit, availability, session-policy and immutable source metadata. No static environment FX rates or absolute-checkout imports.
- Long-only equity/ETF quantities, USD cash, zero cash interest. Reject futures, shorts, leverage, taxes, margin, foreign cash and total-return mode.
- Between transactions, quantities stay fixed; empty schedules, all-cash periods and full liquidations remain in performance output.
- A closing observation cannot be consumed for a signal and filled at that same close. Carried valuation marks cannot become execution prices.
- Costs apply once to modeled traded USD notional. Separate commission, slippage and FX costs; no negative cash or borrowing.
- Fractional buys are capped proportionally within each same-time batch after its sells and costs; integral mode rounds down to each explicit lot. Future sells cannot fund earlier buys.
- Stage A is `diagnostic` / `usd_price_nav`, not total-return or broker execution evidence. Stage B and the research/runtime consumer each need separate follow-up plans.
- Public fixtures are synthetic. Local real-data validation remains private. Worktree → tests/review → PR → merge → verify → delete only current task resources.

## Review Focus

- Asynchronous execution times: a later sale cannot fund an earlier buy; chronology must dominate asset ordering (Tasks 2–3).
- Precision near affordability/lot boundaries: no negative cash, lost residual cash or repeated cost debit (Tasks 2–3).
- Empty/all-cash or unused instruments: do not drop dates or require irrelevant marks; held assets still fail on missing/stale marks (Tasks 1–3).
- Future publication/revised input ordering: choose the most recent eligible observation without using future availability or ambiguous duplicate observations (Task 1).
- Publication capability escalation: a diagnostic multi-decision result must not acquire total-return/order-lifecycle/execution-aware status (Task 4).

## File map — quant-platform

All new source files are modules under `packages/portfolio-backtester/src/portfolio_backtester/`; no new package namespace or packaging-list change is required.

- `usd_ledger_models.py`: request, observation, configuration and result records.
- `usd_ledger_inputs.py`: request validation, causal price/FX selection and unit conversion.
- `usd_ledger_accounting.py`: Decimal valuation, cost calculation, quantity sizing and cash settlement.
- `usd_ledger.py`: event replay, per-instrument holdings and P&L/metrics output.
- `usd_ledger_bundle.py`: diagnostic-only adapter to the existing bundle writer.
- `tests/test_usd_ledger_inputs.py`, `tests/test_usd_ledger_accounting.py`, `tests/test_usd_ledger_replay.py`, `tests/test_usd_ledger_bundle.py`: independent synthetic coverage.
- `docs/reference/usd-price-ledger.md`: public API, units, modeled execution, cash/clock and evidence limits.

## Shared interfaces

Define frozen records in `usd_ledger_models.py`; validate every request in the public replay entry point, including directly constructed records. All money, weights, prices, quantities and cost rates use finite `Decimal`; reject booleans, floats and non-Decimal numerical fields. Use a local precision of 50 digits and round quantity increments down to the supported step. Fractional quantity step is `Decimal("0.000000000001")`; integral mode uses the instrument's positive integer lot.

- `USDInstrument(instrument_id: str, asset_type: str, currency: str, lot_size: int, session_policy_id: str)`; asset type is equity/etf, currency syntax is three uppercase letters, identifiers/policy IDs are nonblank.
- `USDPriceObservation(instrument_id: str, price_at: datetime, available_at: datetime, price: Decimal, unit: str, source_ref: ArtifactRef, availability_basis: str, session_policy_id: str, execution_eligible: bool)`; unit is `currency_per_share`, basis is `verified` or `assumed_date_lag`.
- `USDFXObservation(base_currency: str, quote_currency: str, price_at: datetime, available_at: datetime, rate: Decimal, unit: str, source_ref: ArtifactRef, availability_basis: str)`; unit is `quote_per_base`.
- `USDRebalanceDecision(decision_id: str, clock: ResearchClock, weights: Mapping[str, Decimal], execution_times: Mapping[str, datetime])`. Weights include only selected instruments and sum to at most one; empty means liquidate. Execution-time keys cover the declared instrument universe, so liquidation scheduling is explicit. Validate each time against earliest-order/execution-window bounds. Decisions have strictly increasing decision times and nonoverlapping execution windows.
- `USDReplayConfig(initial_cash: Decimal, sizing_mode: str, commission_bps: Decimal, slippage_bps: Decimal, fx_cost_bps: Decimal, max_price_age: timedelta, max_fx_age: timedelta, fx_pairs: Mapping[str, tuple[str, str]], allow_assumed_availability: bool = False, return_basis: str = "price")`. Initial cash positive; costs nonnegative with combined commission/slippage/FX below 10,000 bps. Modes fractional/integral. Maximum ages positive. The pair selection for each non-USD instrument currency is explicit and resolves directly or by inversion, never by triangulation or source fallback.
- `USDReplayRequest(instruments: tuple[USDInstrument, ...], prices: tuple[USDPriceObservation, ...], fx: tuple[USDFXObservation, ...], decisions: tuple[USDRebalanceDecision, ...], valuation_times: tuple[datetime, ...], config: USDReplayConfig)`. Times are aware UTC, sorted and unique. The nonempty valuation grid must begin at or before the first decision, cover every execution event, and end at or after the last execution. An empty instrument universe is valid for an all-cash run. Retain observation timestamps/source references in outputs.
- `USDReplayResult(daily: pd.DataFrame, holdings: pd.DataFrame, transactions: pd.DataFrame, targets: pd.DataFrame, decision_clocks: tuple[Mapping[str, Any], ...], summary: Mapping[str, Any], diagnostics: Mapping[str, Any])`.
- `USDValidationError(ValueError)` is the public error for invalid inputs, unavailable/stale observations and unsupported capability requests.

### Task 1: Typed inputs and causal marks

**Files:** Create `packages/portfolio-backtester/src/portfolio_backtester/usd_ledger_models.py`, `usd_ledger_inputs.py`; test `tests/test_usd_ledger_inputs.py`.

**Interfaces produced:** `validate_usd_request(request: USDReplayRequest) -> None`; `select_usd_price(request: USDReplayRequest, instrument_id: str, at: datetime, *, execution: bool = False) -> USDPriceObservation`; `select_usd_fx(request: USDReplayRequest, currency: str, at: datetime) -> tuple[Decimal, USDFXObservation | None]`.

- [ ] Write input tests: USD identity conversion equals one; GBPUSD direct rate 1.25 and USDHKD rate 8 both resolve correctly (HKD→USD is 0.125). Require an explicit selected pair for non-USD currencies.
- [ ] Test future-available rows, naive times, invalid units/numbers, unsupported assets/modes, duplicate instrument IDs, duplicate series/time rows, mismatched source series, invalid clocks and overlapping decisions. A future row cannot replace an older eligible row. Missing/older-than-maximum marks fail for held/selected assets; unused/all-cash observations are not required.
- [ ] Test execution selection requires an exact `price_at == execution_time`, `available_at <= execution_time`, execution eligibility and verified session-policy identity. A carried or assumed date-lag observation cannot become an execution mark. Assumed inputs may support diagnostic valuation only when the config explicitly permits them.
- [ ] Run `uv run pytest tests/test_usd_ledger_inputs.py -q`; Expected: FAIL on absent imports/API.
- [ ] Implement records and these functions. Validate `price_at <= available_at`; select maximum eligible price time, enforce age on that time, and reject ambiguous sources. USD identity is explicit; never use parity for other currencies.
- [ ] Rerun the same command; Expected: PASS. Commit `feat: validate causal USD ledger inputs`.

### Task 2: Pure valuation and affordable settlement

**Files:** Create `packages/portfolio-backtester/src/portfolio_backtester/usd_ledger_accounting.py`; test `tests/test_usd_ledger_accounting.py`.

**Interfaces consumed:** Task 1 records and selectors.
**Interfaces produced:** `value_usd_book(quantities: Mapping[str, Decimal], cash: Decimal, local_prices: Mapping[str, Decimal], usd_per_local: Mapping[str, Decimal]) -> tuple[Decimal, Decimal]` returning positions/NAV; `settle_usd_rebalance(quantities: Mapping[str, Decimal], cash: Decimal, desired_quantities: Mapping[str, Decimal], local_prices: Mapping[str, Decimal], usd_per_local: Mapping[str, Decimal], instruments: Mapping[str, USDInstrument], config: USDReplayConfig, *, execution_ids: frozenset[str]) -> tuple[dict[str, Decimal], Decimal, pd.DataFrame]`.

- [ ] Write tests with quantities A=2, local price 10, USD/local 1.5 and cash 70: positions=30, NAV=100. Updating price to 20 keeps quantity 2 and NAV becomes 130.
- [ ] Test affordable USD transactions: buy 5 shares at 10, initial cash 100, commission 100 bps → cash 49.5; liquidate at 10 → cash 99 with another 0.5 cost. No USD-asset FX fee.
- [ ] Test two simultaneous buys with weights 0.5/0.5 at prices 10/20, cash 100 and commission 100 bps: pro-rata scaling yields investment at most 100/1.01; residual cash nonnegative and only one cost debit. Validate within quantity-step rounding bounds.
- [ ] Test integral lot 3 with requested quantity 5 → execute 3; retain residual cash. Partial sell increments round down to the lot; full liquidation may sell the entire held odd lot. Test that a batch changes only execution_ids, preserving quantities for later batches. Reject oversells, negative inventory and costs that can consume the sale notional.
- [ ] Run `uv run pytest tests/test_usd_ledger_accounting.py -q`; Expected: FAIL before implementation.
- [ ] Implement settlement only for execution_ids (desired quantities must cover those IDs), preserving other holdings; use sell-first settlement within one timestamp batch, then scale affordable buy increments together, round down and record each requested/executed delta, cost components, scaling and cash. Do not clamp away material reconciliation errors.
- [ ] Rerun the accounting tests and Task 1 tests; Expected: PASS. Commit `feat: settle USD quantity and cash transactions`.

### Task 3: Chronological quantity replay and attribution

**Files:** Create `packages/portfolio-backtester/src/portfolio_backtester/usd_ledger.py`; test `tests/test_usd_ledger_replay.py`.

**Interfaces produced:** `run_usd_price_replay(request: USDReplayRequest) -> USDReplayResult` in `usd_ledger.py`.

- [ ] Write a three-date synthetic replay: initial cash 100, first target A=0.5 with price 10, no costs; after purchase hold 5 shares and cash 50. At price 20 before another decision, NAV=150 and A weight=2/3. No implicit daily rebalance.
- [ ] Test a GBP asset at constant local price 10: 2 held shares with FX 1.25→1.5 produce exactly 5 USD FX P&L and zero local-price P&L. Test both direct and inverse source representation.
- [ ] Test all-cash run retains every valuation row and returns NAV 100, zero return/drawdown/CAGR, with no invented Sharpe. Test full liquidation and a period without positive-momentum targets do not delete observation dates.
- [ ] Test asynchronous A sale scheduled after B buy: B cannot spend A's future proceeds. Same-time sells precede buys; otherwise chronological timestamps dominate instrument IDs. Reject overlapping rebalance windows rather than combining incompatible targets. Reject grids starting after the first decision or ending before the last execution.
- [ ] Run `uv run pytest tests/test_usd_ledger_replay.py -q`; Expected: FAIL on missing replay.
- [ ] Implement the merged decision/execution/valuation event timeline, using Task 2 accounting. At each decision freeze desired quantities from available pretrade NAV/marks and target weights; execute scheduled increments on their exact eligible marks, using event-time FX and passing only that batch’s execution_ids to settlement. Require decision marks only for existing holdings or positive targets. Unaffordable increments are scaled once and recorded, not silently filled from future cash. Retain quantities until the next actual transaction.
- [ ] Before each decision, execution batch and valuation, update required held-asset marks/FX causally and attribute revaluation to pre-event quantities. Initialize new holdings at their transaction marks so the purchase itself creates no P&L. Attribute revaluation on quantities held before each update: local P&L uses `(P_new-P_old)*F_old*q`, FX P&L uses `P_new*(F_new-F_old)*q`; transactions move cash against inventory, costs reduce NAV. Aggregate event attribution over each valuation interval and enforce reconciled NAV changes.
- [ ] Emit daily columns `valuation_at,cash_usd,positions_usd,nav_usd,local_price_pnl_usd,fx_pnl_usd,costs_usd,nav_return`; per-instrument holdings include quantity, selected price/FX/source times, marked USD value and drifted weight. Record target versus executed quantities and clock/policy identity.
- [ ] Calculate cumulative return, drawdown and actual-calendar CAGR using all valuation rows; omit Sharpe in Stage A. Summary labels `evidence_tier=diagnostic`, `return_basis=usd_price_nav`, `orders_submitted=False`. Reject total-return, dividends/splits and futures inputs before replay.
- [ ] Rerun all three new modules; Expected: PASS. Commit `feat: replay USD holdings with causal valuation and PnL`.

### Task 4: Official diagnostic publication and public guide

**Files:** Create `packages/portfolio-backtester/src/portfolio_backtester/usd_ledger_bundle.py`; test `tests/test_usd_ledger_bundle.py`. Also create `docs/reference/usd-price-ledger.md`.

**Interfaces produced:** `write_usd_price_replay_bundle(output_dir: Path, *, result: USDReplayResult, run_id: str, research_clock: ResearchClock, producer: Mapping[str, Any], configuration_sha256: str, input_refs: Sequence[Mapping[str, Any]]) -> BacktestBundleManifest` in `usd_ledger_bundle.py`.

- [ ] Write tests publishing a synthetic two-decision result, reading it through existing `read_backtest_bundle`, and verifying inventory hashes and diagnostic evidence tier. Reject empty lineage inputs, invalid digests, inconsistent cash/NAV/holdings/attribution and an existing output path.
- [ ] Test publication cannot enable execution-aware or total-return status; keep order-lifecycle capability false and orders/fills empty. Do not call `write_execution_aware_result_bundle`, weaken its one-clock rule or fabricate order IDs/statuses.
- [ ] Run `uv run pytest tests/test_usd_ledger_bundle.py -q`; Expected: FAIL on missing publisher.
- [ ] Adapt aggregate cash/positions/NAV to existing `UnifiedLedger` table names. Keep modeled transactions, detailed holdings, FX/price source references, availability assumptions and every per-decision clock in JSON-compatible diagnostics (Decimal strings). Call `write_backtest_bundle` with tier `DIAGNOSTIC`; retain its immutable/atomic publication and hash verification. The caller-supplied root research clock describes run bounds; it does not replace the per-decision clocks.
- [ ] Require root valuation_at to equal the last valuation time; for nonempty decisions require root decision_at to equal the first decision time, with root execution bounds covering all modeled executions. For an all-cash run require root decision_at at or before the first valuation. Preserve later decisions only in per-decision clocks; do not imply the root information cutoff authorizes their inputs. Reject inconsistent authoritative evidence/capability overrides in summary or diagnostics. Do not attach the diagnostic tables as a full `CanonicalBacktestResult.unified_ledger` with false lifecycle capability.
- [ ] Write `docs/reference/usd-price-ledger.md` with a complete synthetic example, public signatures, unit/direction/age rules, sell/buy chronology, fractional/integral policy and price-only evidence limits. Explain why current date-only real CSVs require timestamp/session inputs before modeled trades; no retiming a carried close into an eligible execution price.
- [ ] Rerun the four new modules plus `tests/test_backtest_bundle.py` and `tests/contracts/test_research_run_manifest.py`; Expected: PASS. Commit `feat: publish reconciled USD diagnostic bundles`.

### Task 5: Verification, review and provider integration

- [ ] In the isolated platform worktree run `uv sync --locked --all-groups`, `uv run ruff check .`, and `uv run pytest`, plus `git diff --check`. Expected: existing and new checks pass; source changes contain only generic modules/tests/docs. Run any existing required type/format gates from the platform CI before opening the PR.
- [ ] Obtain one fresh whole-branch review through executing-plans, covering the five Review Focus conditions and any publication assumptions. Fix consequential findings with failing regression tests, then rerun the full suite.
- [ ] Commit verified work, push the platform branch and open its own PR. After review/CI merge, verify platform main and remove only that feature branch/worktree.
- [ ] Record the merged reachable platform commit and public import path in the competition progress document through a separate documentation PR. No dependency pin may reference an unmerged branch or worktree. This provider delivery does not yet install a consumer or switch baseline results.

## Follow-up plans — independent deliverables

- Research/runtime consumer: pin the merged provider release, consume immutable datasets and clocks, preserve/version the existing local-price signal schedule, run a matched benchmark with the same costs/clock, publish a diagnostic research manifest using existing `build_research_run_manifest`, then hand off target artifacts separately. Keep provider acquisition out of quant-platform and broker execution disabled.
- Stage B: source definitions for splits/dividend entitlement/payment/currency/reinvestment and revisions, cash-flow reconciliation tests, and prevention of adjusted-price/dividend double counting. No total-return label until implemented and validated.
- Futures: separate contract/settlement/margin/cash-ledger extension. Do not route them through Stage A equity quantity accounting.

## Self-review

- Scope: one independently usable provider mechanism plus diagnostic publication; consumer, total-return and futures interfaces remain separate plans as required by ownership.
- Spec coverage: units/clocks/unsupported capabilities in Task 1; cash/costs/rounding in Task 2; fixed quantities, asynchronous events, attribution/all-cash/metrics in Task 3; hashes/clocks/evidence and existing bundle reuse in Task 4; integration gates in Task 5.
- Type consistency: all numerical core fields are Decimal; observation selectors return declared records; settlement result feeds replay; replay result feeds only the diagnostic publisher.
- Execution/source limits: future availability and carried execution marks are rejected. Existing date-only CSVs are not silently relabeled as verified tradable observations. No order-lifecycle or multi-decision execution-aware capability is invented.
- Phase limits: Stage A rejects corporate actions and total-return requests; their tests and source semantics belong to Stage B.
