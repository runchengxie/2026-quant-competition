# Competition MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze a competition-specific configuration and artifact, then safely convert current positions into Paper-only broker-neutral rebalance intents.

**Architecture:** Keep research outside this repository. A checked-in non-secret competition config describes the run, while each immutable run directory contains normalized targets, lineage, resolved config, and evidence. A pure rebalance planner compares target quantities with a position snapshot and emits signed order intents; broker adapters consume those intents without making portfolio decisions.

**Tech Stack:** Python 3.12, dataclasses, JSON, pytest, existing contract and audit packages.

**Spec:** `docs/superpowers/specs/2026-09-03-competition-execution-platform-design.md` and the approved chat design for the competition MVP.

## Global Constraints

- Research code remains outside this repository and crosses the boundary only through `targets.json` and `lineage.json`.
- Windows runner defaults to Paper and dry-run; no test places a real order.
- Live execution requires explicit environment guards and human supervision.
- Existing run artifacts are immutable by default and credentials never enter config or evidence.
- Every production behavior change is introduced by a failing test first.

### Task 1: Add the competition run configuration

**Files:**
- Create: `config/competition-2026-hk.json`
- Create: `tests/test_competition_config.py`

**Interfaces:**
- Produces a JSON object with explicit strategy, market, benchmark, portfolio, eligibility, cost, and execution fields.

- [ ] **Step 1: Write the failing test**

```python
def test_competition_config_is_explicit_and_paper_safe():
    config = json.loads(Path("config/competition-2026-hk.json").read_text())
    assert config["market"] == "HK"
    assert config["benchmark"] == "HSCI"
    assert config["execution"]["environment"] == "paper"
    assert config["execution"]["dry_run"] is True
    assert config["eligibility"]["min_holding_rate"] == 0.5
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `pytest tests/test_competition_config.py -q`
Expected: FAIL because `config/competition-2026-hk.json` does not exist.

- [ ] **Step 3: Add the minimal non-secret JSON configuration**

Use `HK` and `HSCI` as the initial explicit choices, with a comment-free JSON file and a `pending_confirmations` array for rules still awaiting written confirmation.

- [ ] **Step 4: Run the test and verify it passes**

Run: `pytest tests/test_competition_config.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config/competition-2026-hk.json tests/test_competition_config.py
git commit -m "chore: freeze initial competition configuration"
```

### Task 2: Publish immutable frozen run artifacts

**Files:**
- Create: `packages/audit/artifacts.py`
- Create: `tests/audit/test_artifacts.py`
- Modify: `packages/audit/__init__.py`

**Interfaces:**
- `publish_frozen_run(run_root: str | Path, *, targets: Mapping[str, Any], lineage: Mapping[str, Any], config: Mapping[str, Any], metrics: Mapping[str, Any]) -> Path`
- The function creates `targets.json`, `lineage.json`, `resolved-config.json`, `metrics.json`, and `evidence.json`; it raises `FileExistsError` if the run directory already exists.

- [ ] **Step 1: Write the failing tests**

```python
def test_publish_frozen_run_writes_complete_artifact(tmp_path):
    run = publish_frozen_run(tmp_path / "run-001", targets=TARGETS, lineage=LINEAGE,
                             config=CONFIG, metrics={"sharpe": 0.8})
    assert run.joinpath("targets.json").is_file()
    assert json.loads(run.joinpath("evidence.json").read_text())["environment"] == "paper"

def test_publish_frozen_run_does_not_overwrite_existing_run(tmp_path):
    publish_frozen_run(tmp_path / "run-001", targets=TARGETS, lineage=LINEAGE,
                       config=CONFIG, metrics={})
    with pytest.raises(FileExistsError):
        publish_frozen_run(tmp_path / "run-001", targets=TARGETS, lineage=LINEAGE,
                           config=CONFIG, metrics={})
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `pytest tests/audit/test_artifacts.py -q`
Expected: FAIL because `publish_frozen_run` is not defined.

- [ ] **Step 3: Implement the smallest artifact publisher**

Validate the target payload through `NiraTargetHandoff`, validate evidence through `validate_release_evidence`, write JSON with UTF-8 and a final newline, and create the destination only after checking that it does not exist.

- [ ] **Step 4: Run the tests and verify they pass**

Run: `pytest tests/audit/test_artifacts.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/audit tests/audit
git commit -m "feat: publish immutable competition run artifacts"
```

### Task 3: Add signed rebalance planning and Paper adapter support

**Files:**
- Create: `packages/contracts/orders.py`
- Create: `packages/execution_policies/rebalance.py`
- Create: `tests/execution/test_rebalance.py`
- Modify: `adapters/ibkr/events.py`
- Modify: `apps/execution_runner/runner.py`

**Interfaces:**
- `PositionSnapshot = Mapping[str, Decimal]`
- `OrderIntent(order_id: str, symbol: str, side: Literal["BUY", "SELL"], quantity: Decimal)`
- `plan_rebalance(targets: Sequence[ExecutionCandidate], positions: PositionSnapshot) -> tuple[OrderIntent, ...]`
- Positive target-minus-current quantity produces BUY; negative produces SELL; zero produces no intent.

- [ ] **Step 1: Write failing tests**

```python
def test_plan_rebalance_emits_buy_and_sell_deltas():
    intents = plan_rebalance(
        (ExecutionCandidate("0700.HK", Decimal("10"), Decimal("10")),
         ExecutionCandidate("0005.HK", Decimal("2"), Decimal("2"))),
        {"0700.HK": Decimal("4"), "0005.HK": Decimal("5")},
    )
    assert [(i.symbol, i.side, i.quantity) for i in intents] == [
        ("0700.HK", "BUY", Decimal("6")),
        ("0005.HK", "SELL", Decimal("3")),
    ]

def test_plan_rebalance_is_empty_when_positions_match():
    assert plan_rebalance((ExecutionCandidate("0700.HK", Decimal("10"), Decimal("10")),),
                          {"0700.HK": Decimal("10")}) == ()
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `pytest tests/execution/test_rebalance.py -q`
Expected: FAIL because `plan_rebalance` and `OrderIntent` do not exist.

- [ ] **Step 3: Implement the pure planner and adapter direction**

Keep planning independent of IBKR. Add `side` to the adapter’s order creation and submit each intent with its signed direction. Preserve the existing safety guard and never infer fills from `placeOrder` returning.

- [ ] **Step 4: Run focused and regression tests**

Run: `pytest tests/execution/test_rebalance.py tests/adapters/test_ibkr_events.py tests/execution -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/contracts packages/execution_policies tests/execution tests/adapters adapters/ibkr/events.py apps/execution_runner/runner.py
git commit -m "feat: plan safe paper rebalances"
```

### Final verification

- [ ] Run `pytest -q`.
- [ ] Run `python -m strategies.nira.handoff validate --targets <paper-targets.json> --lineage <lineage.json>` with a non-secret sample artifact.
- [ ] Confirm no `.env.local`, credentials, account data, or order logs are staged.
- [ ] Record that IBKR connection, contract qualification, and order lifecycle still require a supervised Paper smoke test.
