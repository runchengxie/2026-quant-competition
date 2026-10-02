# Target Manifest v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Parse and serialize an independent international target manifest with explicit futures identity, and prove the existing execution path rejects it before side effects.

**Architecture:** Add a distinct `TargetManifestV2` and instrument variants in the contracts package. Keep the existing v1 wire reader unchanged; guard the runner's two execution entry points at runtime. Publish a separate v2 JSON Schema and explain which portfolio-level checks require Python validation.

**Tech Stack:** Python 3.12, standard-library dataclasses/Decimal/datetime, pytest, Ruff; JSON Schema validation through a test-only `jsonschema[format-nongpl]>=4.23,<5` dependency.

**Spec:** `docs/superpowers/specs/2026-10-02-target-manifest-v2-design.md`

## Global Constraints

- `TargetSet.from_dict` stays v1-only and rejects v2. No v2-to-v1 conversion, automatic version dispatch, or v2 broker adapter is added.
- No provider requests, broker connection, Paper order submission, or live trading is needed for this contract-only change.
- Keep source in `src/`; use synthetic fixtures, with no account identifiers, licensed raw data, or credentials.
- Required root fields: `schema_version`, `strategy_id`, `as_of`, `reporting_currency`, `targets`; reject additional fields and require nonempty targets.
- Weight and quantity use decimal strings. Weight is between zero and one; all target weights sum to at most one. Present quantities must be positive; futures require an integral contract count.
- Currency format is three uppercase letters; MIC format is four uppercase alphanumeric characters. These checks do not prove code assignment or broker support.
- Futures require contract month, expiry date, multiplier, tick size, roll-rule identity, settlement type, and margin-model identity.
- Preserve v1 reader and serializer behavior. Research run-manifest and lineage ownership remains with `quant-platform`.
- Test locally in the isolated worktree. Use `uv run --locked python -m pytest` with a workspace-local temporary directory.

## Review Focus

- Duck-typed or directly supplied v2 objects reaching execution: both runner methods must reject before broker calls or journal writes.
- Wrong JSON types, unknown nested fields, boolean/numeric decimal inputs: reject with `TargetValidationError`, including malformed root/target/instrument containers.
- Expiry on the as-of UTC date and invalid month/calendar dates: reject conservatively without normalizing impossible dates.
- Different futures months versus repeated instruments: distinguish legitimate separate contracts while rejecting repeated identity even with conflicting metadata.
- Schema/parser disagreement: wire types and variant requirements agree; document cross-row sums, compound uniqueness, and relative expiry as Python-only semantic checks.

---

## File Map

- Create `src/packages/contracts/targets_v2.py`: immutable instrument/target/manifest types, parsing and serialization.
- Modify `src/packages/contracts/__init__.py`: export the v2 types without changing v1 exports.
- Modify `src/apps/execution_runner/runner.py`: shared v1 runtime guard used at the start of `run` and `run_rebalance`.
- Create `schemas/targets.v2.schema.json`: standalone Draft 2020-12 schema; leave `schemas/targets.schema.json` unchanged.
- Create `tests/contracts/test_targets_v2.py`: independent synthetic fixtures and Python validation cases.
- Create `tests/fixtures/targets.v2.valid.json`: one complete synthetic payload shared by contract, schema, and execution-boundary tests; load it with `json.loads` relative to the test directory.
- Create `tests/contracts/test_targets_v2_schema.py`: schema shape and cross-validator checks against the shared JSON fixture.
- Create `tests/execution/test_manifest_version_boundary.py`: execution rejection and zero side-effect tests.
- Modify `pyproject.toml` and `uv.lock`: add and lock the schema validator only in test extras.
- Create `docs/strategy/target-manifest-v2.md`: complete synthetic example and compatibility/validation boundary.

## Task 1: Independent typed v2 contract

**Interfaces:**
- `SecurityInstrumentV2(asset_type: str, symbol: str, market: str, exchange_mic: str, currency: str)` for `equity`/`etf`.
- `FuturesInstrumentV2(asset_type: str, symbol: str, market: str, exchange_mic: str, currency: str, contract_month: str, expiry_date: date, multiplier: Decimal, tick_size: Decimal, roll_rule_id: str, settlement_type: str, margin_model_id: str)` for `future`.
- `TargetV2(instrument: SecurityInstrumentV2 | FuturesInstrumentV2, weight: Decimal, quantity: Decimal | None)`.
- `TargetManifestV2(schema_version: str, strategy_id: str, as_of: datetime, reporting_currency: str, targets: tuple[TargetV2, ...])` with `from_dict(payload: Mapping[str, Any]) -> TargetManifestV2` and `to_dict() -> dict[str, Any]`.
- Use the existing public `TargetValidationError` for all malformed input; do not import private v1 parsing helpers.

- [x] Write the shared fixture with version `2.0`, strategy ID `synthetic-international`, USD reporting currency, and as-of `2026-10-02T08:00:00Z`: US/USD ETF `ETF_TEST` at `XNYS`, JP/JPY equity `EQUITY_TEST` at `XTKS`, and US/USD future `FUT_TEST` at `XCME`. Future metadata: month `202612`, expiry `2026-12-18`, multiplier `50`, tick `0.25`, cash settlement, roll ID `synthetic-roll.v1`, margin model ID `synthetic-margin.v1`, quantity `2`; target weights `0.30`, `0.20`, `0.10`.
- [x] Test typed values and JSON round trip; assert decimal precision and exact v2 fields, including absence of root `market`.
- [x] Test `TargetSet.from_dict(v2_payload)` rejects with TargetValidationError, and the existing v1 fixture still round-trips unchanged.
- [x] Test missing fields at each nesting level, non-object containers, empty targets, unsupported versions/asset types, unknown root/target/instrument keys, and non-string decimal values.
- [x] Test nonpositive quantity/multiplier/tick, fractional futures count, invalid month (`202600`, `202613`), invalid calendar date, expiry equal to or before as-of date, naive/non-UTC as-of, lowercase/malformed currency and MIC.
- [x] Test total weight greater than one, duplicate security identity, duplicate future identity with conflicting multiplier, and acceptance of two distinct future contract months.
- [x] Run `uv run --locked python -m pytest tests/contracts/test_targets_v2.py -q --basetemp .pytest-tmp` and observe failure before implementation.
- [x] Implement parsing in `targets_v2.py` using exact property allowlists and strict string/type checks. Require as-of form `YYYY-MM-DDTHH:MM:SS[.1–6 fractional digits](Z|+00:00)` and validate the resulting calendar/time. Validate date/month shapes before calendar parsing; parse only decimal strings with unsigned plain-decimal syntax. Futures counts must have positive integral value. Require nonblank symbols/identifiers and an uppercase market code matching `[A-Z][A-Z0-9_-]*`.
- [x] Serialize Decimal fields as strings and UTC time as ISO format with `Z`; preserve instrument identity and variant metadata. Reject duplicate keys `(asset_type, market, exchange_mic, symbol[, contract_month])` and validate total weight after individual targets.
- [x] Export new types; rerun focused tests and existing `tests/contracts/test_targets.py` to green.

## Task 2: Enforce v1 at execution entry points

**Interfaces:**
- An internal runner guard requires `isinstance(value, TargetSet)` and `value.schema_version == "1.0"`, otherwise raises `TargetValidationError("execution requires a v1 TargetSet")`.
- Keep `run` and `run_rebalance` public signatures accepting `TargetSet`; callers must not rely on annotations for runtime protection.

- [x] Write parameterized tests for both runner methods with dry-run enabled and disabled, using an actual parsed v2 manifest and a submission spy. Assert rejection, zero `submit`/`submit_intents` calls, and no journal file/order event.
- [x] Add a duck-typed fake exposing `.targets` with valid legacy-style target fields to prove the check occurs before candidate preparation; add a directly constructed `TargetSet` carrying a non-v1 version.
- [x] Test the existing Nira wire loader rejects a v2 payload without changing loader behavior.
- [x] Run `uv run --locked python -m pytest tests/execution/test_manifest_version_boundary.py -q --basetemp .pytest-tmp` and observe failure before the guard.
- [x] Add the shared guard as the first operation in both runner methods, before target inspection or rebalance planning; do not add futures routing.
- [x] Rerun boundary tests and the existing execution/handoff tests to green.

## Task 3: Publish and verify the v2 JSON Schema

**Interfaces:**
- `schemas/targets.v2.schema.json` is Draft 2020-12 with const version `2.0`, strict root/target/instrument properties, and discriminated security/futures variants.
- `Draft202012Validator(schema, format_checker=FormatChecker(formats=["date", "date-time"]))` validates shared wire fixtures in tests.

- [x] Add `jsonschema[format-nongpl]>=4.23,<5` to the `test` extra and run `uv lock`, then `uv sync --locked --extra test`. It must not enter runtime dependencies.
- [x] Write schema tests that first require the new schema file, validate schema correctness, accept the mixed fixture and each security type, and reject missing futures fields, extra fields, numeric decimal values, malformed dates/months/currency/MIC, and zero/fractional future quantity.
- [x] Run schema tests and observe failure from the missing schema.
- [x] Create the schema: root targets `minItems: 1`; `oneOf` instrument variants; `additionalProperties: false` throughout. Security quantity is a positive decimal string; future quantity is required and positive integral decimal string (allow trailing zero fractional digits if the numeric value is integral). Match Python wire patterns and require nonblank text.
- [x] Include a schema description explaining that Python validation also enforces aggregate weights, compound identities, and expiry relative to the manifest date. JSON Schema `format` checking is required for timestamps/calendar dates.
- [x] Rerun parser and schema tests on the shared syntactic cases; keep semantic-only negative cases in Python tests.

## Task 4: Documentation, local verification, and review

**Files:** `docs/strategy/target-manifest-v2.md`, implementation plan status.

- [x] Document the complete synthetic payload, type/API usage, decimal preservation, conservative expiry rule, and schema versus Python validation scope. State that explicit v2 parsing does not enable execution.
- [x] Document that MIC is instrument identity rather than an IBKR routing exchange; later qualification must map it explicitly. Currency syntax and metadata do not establish current permissions or broker margin.
- [x] Run `uv run --locked ruff check src tests`, `uv run --locked python -m pytest -q --basetemp .pytest-tmp`, `uv run --locked python -m compileall -q src`, and `git diff --check`.
- [x] Review the entire diff for unexpected v1 changes, installed runtime dependencies, raw provider data, and any v2-to-v1 coercion. Obtain a fresh contract/execution-boundary review and fix consequential findings with regression tests.
- [ ] Commit the verified work, then follow the user's PR → merge main → delete feature branch/worktree workflow. Recheck main after merge; keep unrelated branches and stashes intact.

## Self-review

- Spec coverage: typed fields and round-trip behavior are in Task 1; execution and v1 handoff protection in Task 2; schema requirements and precision in Task 3; public usage and actual metadata limits in Task 4.
- Type consistency: separate immutable instrument variants feed `TargetV2`; only `TargetManifestV2` holds them. Legacy runner methods still require `TargetSet`; no union reader is introduced.
- Review Focus coverage: type/side-effect cases are owned by Task 2; malformed containers, dates, decimals, expiry and compound identity by Task 1; schema agreement and semantic limits by Task 3.
- Runtime checks supplement the approved boundary rather than adding v2 execution. The root's empty-array illustration is explicitly illustrative; real manifests require targets.
- The JSON Schema cannot express cross-row sum/compound identity or relative expiry in standard Draft 2020-12, so the plan tests and documents those as Python-only checks rather than claiming full equivalence.

## Implementation verification

Implemented in the isolated feature worktree. Full suite: 277 passed; Ruff, compileall and diff checks passed. An independent whole-branch reviewer found no Critical, Important or Minor issues. The reviewer independently ran 135 new tests and exercised 624 malformed-type substitutions. PR integration and cleanup are recorded in GitHub and the session after this commit. No v2 broker execution was added.
