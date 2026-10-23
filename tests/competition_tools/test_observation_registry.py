"""Freeze is not collection; local hashes cannot prove external timestamps."""

import copy
from datetime import datetime, timezone

import pytest

from competition_tools.datasets.storage import digest, write_json
from competition_tools.evaluation.study_identity import source_identity


def fixture_protocol(tmp_path):
    from test_ablation_source import fixture_repo
    from competition_tools.evaluation.observation_registry import CANDIDATES
    from competition_tools.evaluation.controls.catalog import COSTS

    source = fixture_repo(tmp_path / "source")
    warmup = {}
    for market in ("US", "crypto"):
        path = tmp_path / (market + ".json")
        from datetime import date, timedelta

        start = date(2024, 12, 31) - timedelta(days=251)
        dates = [(start + timedelta(days=i)).isoformat() for i in range(252)]
        write_json(path, dict(dates=dates, close={"A": [100.0] * 252}))
        warmup[market] = dict(path=str(path), sha256=digest(path))
    return dict(
        schema="competition.observation_protocol.v1",
        synthetic=True,
        candidates=copy.deepcopy(CANDIDATES),
        costs=copy.deepcopy(COSTS),
        warmup=warmup,
        source_identity=source_identity(source),
        known_cutoff="2024-12-31T23:59:59Z",
        initial_nav=1,
        valuation="lagged_close_proxy",
        zero_volatility="cash",
        execution_authorized=False,
    )


def test_freeze_does_not_claim_observation_started(tmp_path):
    from competition_tools.evaluation.observation_registry import (
        freeze_observation,
        inspect_observation,
    )

    protocol = fixture_protocol(tmp_path)
    root = tmp_path / "registry"
    value = freeze_observation(
        protocol, root, now=datetime(2025, 1, 1, tzinfo=timezone.utc)
    )
    assert value["status"] == "awaiting_new_data"
    assert value["first_eligible_observation_at"] is None
    assert value["observations"] == 0
    assert inspect_observation(root) == value
    from competition_tools.evaluation.controls.contracts import read_json

    frozen = read_json(root / "protocol.json")
    assert frozen["rules"]["new_dates_per_import"] == 512
    assert frozen["rules"]["seconds_per_import"] == 3600
    assert "changed_account_prefix" in frozen["rules"]["stop_conditions"]
    with pytest.raises(FileExistsError):
        freeze_observation(
            protocol, root, now=datetime(2025, 1, 2, tzinfo=timezone.utc)
        )


@pytest.mark.parametrize("mutation", ["backdated", "policy", "source", "warmup"])
def test_invalid_freeze_writes_no_registry(tmp_path, mutation):
    from competition_tools.evaluation.observation_registry import freeze_observation

    protocol = fixture_protocol(tmp_path)
    if mutation == "backdated":
        protocol["known_cutoff"] = "2025-01-02T00:00:00Z"
    elif mutation == "policy":
        protocol["candidates"]["US"] = ["ew_daily"]
    elif mutation == "source":
        protocol["source_identity"]["source_sha256"] = "0" * 64
    else:
        protocol["warmup"]["US"]["sha256"] = "0" * 64
    root = tmp_path / "registry"
    with pytest.raises(ValueError):
        freeze_observation(
            protocol, root, now=datetime(2025, 1, 1, tzinfo=timezone.utc)
        )
    assert not root.exists()


def test_prior_source_or_warmup_mutation_is_visible(tmp_path):
    from competition_tools.evaluation.observation_registry import (
        freeze_observation,
        inspect_observation,
    )

    protocol = fixture_protocol(tmp_path)
    root = tmp_path / "registry"
    freeze_observation(protocol, root, now=datetime(2025, 1, 1, tzinfo=timezone.utc))
    from pathlib import Path

    Path(protocol["warmup"]["US"]["path"]).write_text("{}")
    with pytest.raises(ValueError):
        inspect_observation(root)


def frozen_import(tmp_path):
    import json
    from pathlib import Path
    from competition_tools.evaluation.observation_registry import freeze_observation

    protocol = fixture_protocol(tmp_path)
    root = tmp_path / "registry"
    status = freeze_observation(
        protocol, root, now=datetime(2025, 1, 1, tzinfo=timezone.utc)
    )
    bars = json.loads(Path(protocol["warmup"]["crypto"]["path"]).read_text())
    bars["dates"].append("2025-01-01")
    bars["close"]["A"].append(101.0)
    value = dict(
        schema="competition.observation_import.v1",
        protocol_id=status["protocol_id"],
        market="crypto",
        synthetic=True,
        price_basis="raw",
        quote_currency="USDT",
        availability_basis="synthetic",
        availability_evidence=None,
        available_at=["2025-01-02T00:01:00Z"],
        bars=bars,
    )
    return root, value


@pytest.mark.parametrize(
    "mutation", ["unknown", "old_tail", "future", "gap", "policy", "lock"]
)
def test_invalid_import_never_starts_child_or_accepts_receipt(
    tmp_path, monkeypatch, mutation
):
    from competition_tools.evaluation import observation_registry as registry
    from competition_tools.team.config import TeamConfig

    root, value = frozen_import(tmp_path)
    if mutation == "unknown":
        value["availability_basis"] = "unknown"
    elif mutation == "old_tail":
        value["available_at"] = ["2024-12-31T23:59:59Z"]
    elif mutation == "future":
        value["available_at"] = ["2025-01-04T00:01:00Z"]
    elif mutation == "gap":
        value["bars"]["dates"][-1] = "2025-01-02"
        value["available_at"] = ["2025-01-03T00:01:00Z"]
    elif mutation == "policy":
        value["candidate"] = "winner_after_seeing_history"
    else:
        (root / ".lock").write_text("busy")
    path = tmp_path / "import.json"
    write_json(path, value)
    monkeypatch.setattr(
        registry,
        "_run_replay",
        lambda *a, **k: pytest.fail("invalid import started child"),
    )
    with pytest.raises(ValueError):
        registry.append_observation(
            root,
            path,
            config=TeamConfig(tmp_path / "data", tmp_path / "envs"),
            now=datetime(2025, 1, 3, 12, tzinfo=timezone.utc),
        )
    assert not list((root / "imports").glob("*/receipt.json"))


def cash_replay(config, project, request_path, output_path, timeout):
    """Journal boundary fixture; policy economics are tested in installed leaves."""
    from competition_tools.evaluation.controls.contracts import read_json
    from competition_tools.evaluation.observation_registry import CANDIDATES
    from competition_tools.evaluation.controls.catalog import COSTS

    request = read_json(request_path)
    market = request["market"]
    periods = [
        dict(
            date=d,
            equity=1.0,
            cash=1.0,
            positions={p: 0.0 for p in request["bars"]["close"]},
            weights={p: 0.0 for p in request["bars"]["close"]},
            turnover=0.0,
            cost=0.0,
            net_return=0.0,
            exposure=0.0,
        )
        for d in request["bars"]["dates"][252:]
    ]
    metrics = {
        k: 0.0
        for k in "net_return gross_return cost_drag volatility max_drawdown turnover total_costs mean_daily_turnover mean_exposure".split()
    }
    metrics.update(periods=len(periods), flat_days=len(periods), sharpe=None)
    account = dict(
        accounting_model="self_financing_daily.v1",
        quote_currency="USDT" if market == "crypto" else "USD",
        periods=periods,
    )
    result = dict(
        schema="competition.observation_replay_result.v1",
        protocol_id=request["protocol_id"],
        request_sha256=digest(request_path),
        expected_leaf_sha256=request["expected_leaf_sha256"],
        market=market,
        results=[
            dict(
                arm_id=a,
                fee_bps=f,
                output=dict(
                    net=copy.deepcopy(account),
                    gross=copy.deepcopy(account),
                    metrics=copy.deepcopy(metrics),
                    diagnostics={},
                ),
            )
            for a in CANDIDATES[market]
            for f in COSTS[market]
        ],
    )
    write_json(output_path, result)


def test_exact_and_offset_duplicates_are_idempotent_and_prefix_is_immutable(
    tmp_path, monkeypatch
):
    from competition_tools.evaluation import observation_registry as registry
    from competition_tools.team.config import TeamConfig

    root, value = frozen_import(tmp_path)
    monkeypatch.setattr(registry, "_run_replay", cash_replay)
    path = tmp_path / "first.json"
    write_json(path, value)
    config = TeamConfig(tmp_path / "data", tmp_path / "envs")
    now = datetime(2025, 1, 4, tzinfo=timezone.utc)
    first = registry.append_observation(root, path, config=config, now=now)
    assert first["observations"] == 1
    assert first["status"] == "observing"
    assert registry.append_observation(root, path, config=config, now=now) == first
    value["available_at"][0] = "2025-01-02T08:01:00+08:00"
    offset = tmp_path / "offset.json"
    write_json(offset, value)
    assert registry.append_observation(root, offset, config=config, now=now) == first
    value["bars"]["dates"].append("2025-01-02")
    value["bars"]["close"]["A"].append(102.0)
    value["available_at"].append("2025-01-03T00:01:00Z")
    second_path = tmp_path / "second.json"
    write_json(second_path, value)
    second = registry.append_observation(root, second_path, config=config, now=now)
    assert second["observations"] == 2
    assert len(list((root / "imports").glob("*/receipt.json"))) == 2
    value["bars"]["close"]["A"][-2] = 999.0
    conflict = tmp_path / "conflict.json"
    write_json(conflict, value)
    with pytest.raises(ValueError):
        registry.append_observation(root, conflict, config=config, now=now)
    assert registry.inspect_observation(root) == second


def test_budget_is_per_extension_and_account_can_cross_512_total_dates(
    tmp_path, monkeypatch
):
    from datetime import date, timedelta
    from competition_tools.evaluation import observation_registry as registry
    from competition_tools.team.config import TeamConfig

    root, value = frozen_import(tmp_path)
    monkeypatch.setattr(registry, "_run_replay", cash_replay)
    config = TeamConfig(tmp_path / "data", tmp_path / "envs")
    now = datetime(2027, 1, 1, tzinfo=timezone.utc)
    warmup = copy.deepcopy(value["bars"])
    for count in (512, 513):
        dates = [
            (date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(count)
        ]
        value["bars"] = dict(
            dates=warmup["dates"][:252] + dates,
            close={"A": warmup["close"]["A"][:252] + [101.0] * count},
        )
        value["available_at"] = [
            (
                datetime(2025, 1, 2, 0, 1, tzinfo=timezone.utc) + timedelta(days=i)
            ).isoformat()
            for i in range(count)
        ]
        path = tmp_path / f"import-{count}.json"
        write_json(path, value)
        result = registry.append_observation(root, path, config=config, now=now)
        assert result["observations"] == count


def test_observation_help_does_not_load_configuration(capsys):
    from competition_tools.team.__main__ import main

    with pytest.raises(SystemExit) as exc:
        main(["observe", "--help"])
    assert exc.value.code == 0
    assert "--registry-root" in capsys.readouterr().out


def test_exhausted_economic_import_cannot_reset_budget_by_retimestamping(
    tmp_path, monkeypatch
):
    from competition_tools.evaluation import observation_registry as registry
    from competition_tools.team.config import TeamConfig

    root, value = frozen_import(tmp_path)
    path = tmp_path / "first.json"
    write_json(path, value)
    clock, calls = [0.0], []
    monkeypatch.setattr(registry.time, "monotonic", lambda: clock[0])

    def slow(*args):
        calls.append(args)
        cash_replay(*args)
        clock[0] = 3601.0

    monkeypatch.setattr(registry, "_run_replay", slow)
    config = TeamConfig(tmp_path / "data", tmp_path / "envs")
    now = datetime(2025, 1, 3, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="TIME_BUDGET"):
        registry.append_observation(root, path, config=config, now=now)
    value["available_at"] = ["2025-01-02T00:01:01Z"]
    revised = tmp_path / "retimestamped.json"
    write_json(revised, value)
    clock[0] = 0.0
    with pytest.raises(ValueError, match="SPEND_UNKNOWN_OR_ALREADY_ATTEMPTED"):
        registry.append_observation(root, revised, config=config, now=now)
    assert len(calls) == 1
    assert registry.inspect_observation(root)["observations"] == 0


def test_child_timeout_is_stable_and_does_not_accept_a_receipt(tmp_path, monkeypatch):
    import subprocess
    from competition_tools.evaluation import observation_registry as registry
    from competition_tools.team.config import TeamConfig

    root, value = frozen_import(tmp_path)
    path = tmp_path / "import.json"
    write_json(path, value)

    def timeout(*args):
        raise subprocess.TimeoutExpired(["private-command"], 1)

    monkeypatch.setattr(registry, "_run_replay", timeout)
    with pytest.raises(ValueError, match="OBSERVATION_CHILD_TIMEOUT"):
        registry.append_observation(
            root,
            path,
            config=TeamConfig(tmp_path / "data", tmp_path / "envs"),
            now=datetime(2025, 1, 3, tzinfo=timezone.utc),
        )
    assert registry.inspect_observation(root)["observations"] == 0


def test_acceptance_does_not_hide_expensive_postcommit_validation(
    tmp_path, monkeypatch
):
    from competition_tools.evaluation import observation_registry as registry
    from competition_tools.team.config import TeamConfig

    root, value = frozen_import(tmp_path)
    path = tmp_path / "import.json"
    write_json(path, value)
    clock = [0.0]
    monkeypatch.setattr(registry.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(registry, "_run_replay", cash_replay)
    original = registry._history

    def expensive_read(root, protocol):
        rows = original(root, protocol)
        if rows:
            clock[0] += 3601.0
        return rows

    monkeypatch.setattr(registry, "_history", expensive_read)
    result = registry.append_observation(
        root,
        path,
        config=TeamConfig(tmp_path / "data", tmp_path / "envs"),
        now=datetime(2025, 1, 3, tzinfo=timezone.utc),
    )
    assert result["observations"] == 1
    assert clock[0] < 3600


def test_a_hash_valid_warmup_still_requires_a_complete_causal_grid(tmp_path):
    from datetime import date, timedelta
    from pathlib import Path
    from competition_tools.evaluation import observation_registry as registry
    from competition_tools.evaluation.controls.contracts import read_json

    protocol = fixture_protocol(tmp_path)
    path = Path(protocol["warmup"]["crypto"]["path"])
    bars = read_json(path)
    bars["dates"][0] = (
        date.fromisoformat(bars["dates"][0]) - timedelta(days=1)
    ).isoformat()
    write_json(path, bars)
    protocol["warmup"]["crypto"]["sha256"] = digest(path)
    with pytest.raises(ValueError, match="WARMUP_GRID"):
        registry.freeze_observation(
            protocol,
            tmp_path / "registry",
            now=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize("changed", ["source_import", "receipt", "result"])
def test_accepted_receipts_and_original_bytes_are_rechecked(
    tmp_path, monkeypatch, changed
):
    from competition_tools.evaluation import observation_registry as registry
    from competition_tools.team.config import TeamConfig

    root, value = frozen_import(tmp_path)
    path = tmp_path / "import.json"
    write_json(path, value)
    monkeypatch.setattr(registry, "_run_replay", cash_replay)
    registry.append_observation(
        root,
        path,
        config=TeamConfig(tmp_path / "data", tmp_path / "envs"),
        now=datetime(2025, 1, 3, tzinfo=timezone.utc),
    )
    target = (
        path
        if changed == "source_import"
        else root / "imports/000001" / (changed + ".json")
    )
    target.write_text("{}")
    with pytest.raises(ValueError):
        registry.inspect_observation(root)


def real_us_import(
    tmp_path, monkeypatch, *, available="2025-01-03T00:01:00Z", wrong_context=False
):
    from pathlib import Path
    from competition_tools.datasets.session_calendar import completed_sessions
    from competition_tools.evaluation import observation_registry as registry
    from competition_tools.evaluation.controls.contracts import read_json
    from competition_tools.evaluation.study_identity import canonical_hash

    template = fixture_protocol(tmp_path)
    template["synthetic"] = False
    path = Path(template["warmup"]["US"]["path"])
    dates = completed_sessions(
        "XNYS",
        "2023-01-01",
        "2024-12-31",
        as_of=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )["sessions"][-252:]
    write_json(path, dict(dates=dates, close={"A": [100.0] * 252}))
    template["warmup"]["US"]["sha256"] = digest(path)
    root = tmp_path / "registry"
    status = registry.freeze_observation(
        template, root, now=datetime(2025, 1, 1, tzinfo=timezone.utc)
    )
    bars = read_json(path)
    bars["dates"].append("2025-01-02")
    bars["close"]["A"].append(101.0)
    value = dict(
        schema="competition.observation_import.v1",
        protocol_id=status["protocol_id"],
        market="US",
        synthetic=False,
        price_basis="split_adjusted",
        quote_currency="USD",
        availability_basis="verified",
        availability_evidence=None,
        available_at=[registry.utc_time(available).isoformat()],
        bars=bars,
    )
    evidence = dict(
        schema="competition.observation_availability_review.v1",
        protocol_id=value["protocol_id"],
        market="US",
        import_sha256="0" * 64
        if wrong_context
        else canonical_hash(
            {k: v for k, v in value.items() if k != "availability_evidence"}
        ),
        decision="verified",
        reviewed_at="2025-01-03T10:00:00Z",
    )
    evidence_path = tmp_path / "availability-review.json"
    write_json(evidence_path, evidence)
    value["availability_evidence"] = dict(
        path=str(evidence_path), sha256=digest(evidence_path)
    )
    monkeypatch.setattr(
        registry, "TRUSTED_AVAILABILITY_EVIDENCE", frozenset({digest(evidence_path)})
    )
    return root, value


def test_reviewed_availability_cannot_be_reused_for_another_import(
    tmp_path, monkeypatch
):
    from competition_tools.evaluation import observation_registry as registry

    root, value = real_us_import(tmp_path, monkeypatch, wrong_context=True)
    with pytest.raises(ValueError, match="AVAILABILITY_REVIEW_CONTEXT"):
        registry._normalize_import(
            value,
            registry._protocol(root),
            now=datetime(2025, 1, 3, 12, tzinfo=timezone.utc),
        )


def test_real_us_availability_can_follow_close_on_the_same_utc_date(
    tmp_path, monkeypatch
):
    from competition_tools.evaluation import observation_registry as registry

    root, value = real_us_import(
        tmp_path, monkeypatch, available="2025-01-02T21:01:00Z"
    )
    normalized = registry._normalize_import(
        value,
        registry._protocol(root),
        now=datetime(2025, 1, 3, 12, tzinfo=timezone.utc),
    )
    assert normalized["available_at"] == ["2025-01-02T21:01:00+00:00"]


def test_real_availability_evidence_is_rehashed_after_acceptance(tmp_path, monkeypatch):
    from pathlib import Path
    from competition_tools.evaluation import observation_registry as registry
    from competition_tools.team.config import TeamConfig

    root, value = real_us_import(tmp_path, monkeypatch)
    path = tmp_path / "real-import.json"
    write_json(path, value)
    monkeypatch.setattr(registry, "_run_replay", cash_replay)
    registry.append_observation(
        root,
        path,
        config=TeamConfig(tmp_path / "data", tmp_path / "envs"),
        now=datetime(2025, 1, 3, 12, tzinfo=timezone.utc),
    )
    Path(value["availability_evidence"]["path"]).write_text("{}")
    with pytest.raises(ValueError, match="AVAILABILITY_UNVERIFIED"):
        registry.inspect_observation(root)
