"""A successful process is insufficient evidence of a valid experiment."""

from copy import deepcopy
import json
import subprocess
import sys

import pytest

from competition_tools.experiment_acceptance import (
    assess_experiment,
    canonical_digest,
    public_acceptance_summary,
)
from test_research_acceptance import receipt


def experiment(tmp_path):
    source = receipt(tmp_path)
    summary = {
        "strategy_id": "equal_weight",
        "run_status": "completed",
        "fallback_reasons": [],
        "metrics": {"total_return": 0.01},
    }
    observations = [{"date": "2026-01-02", "code": "HK.TEST", "target_weight": 1.0}]
    plan = {
        "schema_version": "competition.experiment_plan.v1",
        "purpose": "software_diagnostic",
        "evaluation_kind": "retrospective",
        "strategy_id": "equal_weight",
        "config": {"window": 20},
        "config_fingerprint": canonical_digest({"window": 20}),
        "input_fingerprint": source["fingerprint"],
        "output_fingerprint": canonical_digest(
            {"summary": summary, "observations": observations}
        ),
        "sample_interval": {"start": "2026-01-01", "end": "2026-01-03"},
        "windows": {
            "training": None,
            "validation": None,
            "evaluation": {"start": "2026-01-02", "end": "2026-01-03"},
        },
        "minimum_universe": 1,
        "minimum_observations": 1,
        "costs": {
            "fee_bps": 30.0,
            "slippage_bps": 0.0,
            "currency": "HKD",
            "verified": False,
        },
        "history_exposed": True,
        "owner_protocol_receipt": None,
    }
    return plan, source, summary, observations


def refresh(plan, summary, observations):
    plan["output_fingerprint"] = canonical_digest(
        {"summary": summary, "observations": observations}
    )


def test_valid_software_diagnostic_preserves_original_metrics(tmp_path):
    args = experiment(tmp_path)
    before = deepcopy(args)
    result = assess_experiment(*args)
    assert result["status"] == "accepted_diagnostic"
    assert result["sample_counts"] == {
        "observations": 1,
        "universe": 1,
        "active_observations": 1,
        "folds": 0,
    }
    assert "SYNTHETIC_INPUT" in result["issue_codes"]
    assert args == before


@pytest.mark.parametrize(
    "change,code",
    [
        ({"run_status": "fallback"}, "RUN_NOT_COMPLETED"),
        ({"fallback_reasons": ["insufficient warmup"]}, "FALLBACK_USED"),
    ],
)
def test_summary_success_cannot_hide_fallback(tmp_path, change, code):
    plan, source, summary, rows = experiment(tmp_path)
    summary.update(change)
    refresh(plan, summary, rows)
    result = assess_experiment(plan, source, summary, rows)
    assert result["status"] == "blocked"
    assert code in result["issue_codes"]


@pytest.mark.parametrize(
    "strategy,weight,code",
    [
        ("cnn_pattern", 0.0, "NO_POSITIONS"),
        ("cnn_walk_forward_rank", 1.0, "NO_ELIGIBLE_FOLDS"),
    ],
)
def test_empty_positions_and_no_folds_are_blocked(tmp_path, strategy, weight, code):
    plan, source, summary, rows = experiment(tmp_path)
    plan["strategy_id"] = summary["strategy_id"] = strategy
    rows[0]["target_weight"] = weight
    refresh(plan, summary, rows)
    result = assess_experiment(plan, source, summary, rows)
    assert result["status"] == "blocked"
    assert code in result["issue_codes"]


def test_overlap_and_inadequate_coverage_ignore_positive_metric(tmp_path):
    plan, source, summary, rows = experiment(tmp_path)
    plan["windows"]["training"] = {"start": "2026-01-01", "end": "2026-01-02"}
    plan.update(minimum_universe=2, minimum_observations=2)
    result = assess_experiment(plan, source, summary, rows)
    assert result["status"] == "blocked"
    assert {
        "WINDOW_OVERLAP",
        "INSUFFICIENT_UNIVERSE",
        "INSUFFICIENT_OBSERVATIONS",
    } <= set(result["issue_codes"])


def test_owner_boolean_or_exposed_history_cannot_promote_research(tmp_path):
    plan, source, summary, rows = experiment(tmp_path)
    plan.update(
        purpose="research_evidence",
        evaluation_kind="owner_unexposed",
        owner_protocol_receipt={"verified": True},
    )
    result = assess_experiment(plan, source, summary, rows)
    assert result["status"] == "blocked"
    assert {
        "OWNER_CONTRACT_VALIDATION_UNAVAILABLE",
        "EXPOSED_HISTORY",
        "UNVERIFIED_COSTS",
        "UNVERIFIED_AVAILABILITY",
    } <= set(result["issue_codes"])


@pytest.mark.parametrize(
    "field", ["config_fingerprint", "input_fingerprint", "output_fingerprint"]
)
def test_fingerprints_must_match_actual_payload(tmp_path, field):
    args = experiment(tmp_path)
    args[0][field] = "0" * 64
    result = assess_experiment(*args)
    assert result["status"] == "blocked"
    assert field.upper() + "_MISMATCH" in result["issue_codes"]


@pytest.mark.parametrize(
    "change",
    [
        {"minimum_universe": True},
        {"costs": {"fee_bps": float("nan")}},
        {"unexpected": True},
    ],
)
def test_malformed_plan_rejected(tmp_path, change):
    args = experiment(tmp_path)
    args[0].update(change)
    with pytest.raises(ValueError):
        assess_experiment(*args)


def test_crypto_units_and_nonfinite_metrics_blocked(tmp_path):
    plan, source, summary, rows = experiment(tmp_path)
    from competition_tools.research_acceptance import receipt_fingerprint

    source["market"] = "CRYPTO"
    source["fingerprint"] = receipt_fingerprint(source)
    plan["input_fingerprint"] = source["fingerprint"]
    summary["metrics"] = {
        "total_pnl": 1.0,
        "fee_cashflow": 0.0,
        "max_absolute_inventory": 1.0,
        "fill_count": 1,
        "total_return": 0.5,
    }
    rows[:] = [{"datetime": "2026-01-02", "inventory": 1.0}]
    refresh(plan, summary, rows)
    result = assess_experiment(plan, source, summary, rows)
    assert result["status"] == "blocked"
    assert {"UNKNOWN_PNL_UNIT", "RETURN_WITHOUT_CAPITAL"} <= set(result["issue_codes"])
    summary["metrics"]["total_pnl"] = float("inf")
    with pytest.raises(ValueError):
        assess_experiment(plan, source, summary, rows)


def test_public_projection_rejects_unknown_fields_and_private_content(tmp_path):
    value = assess_experiment(*experiment(tmp_path))
    assert public_acceptance_summary(value) == value
    for extra in ("dataset_root", "error", "files", "author"):
        with pytest.raises(ValueError):
            public_acceptance_summary(value | {extra: "C:/private/account"})
    changed = deepcopy(value)
    changed["issue_codes"] = ["C:/private/account"]
    with pytest.raises(ValueError):
        public_acceptance_summary(changed)


@pytest.mark.parametrize(
    "change", [{"metrics": {"total_return": "NaN"}}, {"positions_rows": 200}]
)
def test_completed_summary_must_match_actual_observations(tmp_path, change):
    plan, source, summary, rows = experiment(tmp_path)
    summary.update(change)
    refresh(plan, summary, rows)
    with pytest.raises(ValueError):
        assess_experiment(plan, source, summary, rows)


def test_cli_rehashes_inputs_and_does_not_overwrite(tmp_path):
    plan, source, summary, rows = experiment(tmp_path)
    paths = []
    for name, value in zip(
        ("plan", "input-receipt", "summary", "observations"),
        (plan, source, summary, rows),
        strict=True,
    ):
        path = tmp_path / (name + ".json")
        path.write_text(json.dumps(value))
        paths.extend(["--" + name, str(path)])
    command = [sys.executable, "-m", "competition_tools.experiment_acceptance"]
    assert subprocess.run(command + ["--help"], capture_output=True).returncode == 0
    output = tmp_path / "acceptance.json"
    command += paths + ["--dataset-root", str(tmp_path), "--output", str(output)]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    before = output.read_bytes()
    assert subprocess.run(command, capture_output=True).returncode == 2
    assert output.read_bytes() == before
    (tmp_path / "bars.csv").write_bytes(b"changed")
    command[-1] = str(tmp_path / "changed-result.json")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2
    assert "FILE_CHANGED" in result.stdout
    assert str(tmp_path) not in result.stdout + result.stderr
