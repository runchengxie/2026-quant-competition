"""Controls are an opt-in contract, independent of historical ablations."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from competition_tools.evaluation.controls.catalog import ARMS, arm_spec
from competition_tools.evaluation.controls.contracts import load_spec, validate_spec


def controls_spec(tmp_path):
    from competition_tools.datasets.storage import digest

    manifests = {}
    for market in ("US", "crypto"):
        path = tmp_path / (market + ".json")
        path.write_text("{}", encoding="utf-8")
        manifests[market] = str(path)
    return dict(
        schema="competition.strategy_controls_spec.v1",
        manifests=manifests,
        expected_input_hashes={m: digest(Path(p)) for m, p in manifests.items()},
        arms=copy.deepcopy(ARMS),
        costs={"US": [20, 40], "crypto": [0, 10, 25]},
        role="retrospective",
        accepted_research=False,
        budget={"jobs": 512, "seconds": 3600, "batch_jobs": 384},
    )


def test_old_catalog_stays_valid_after_loading_controls(tmp_path):
    from test_ablation_runner import frozen
    from competition_tools.evaluation.ablation_catalog import CATALOG_SHA256, catalog
    from competition_tools.evaluation.study_identity import canonical_hash
    from competition_tools.evaluation.ablation_plan import validate_ablation_job

    old = canonical_hash(catalog())
    plan, _, _ = frozen(tmp_path)
    assert len(ARMS["US"]) == 6 and len(ARMS["crypto"]) == 8
    assert canonical_hash(catalog()) == old == CATALOG_SHA256
    for job in plan["jobs"]:
        validate_ablation_job(job)


@pytest.mark.parametrize(
    "mutation", ["unknown", "bool", "fee", "duplicate", "arm", "hash", "role"]
)
def test_controls_spec_is_strict(tmp_path, mutation):
    spec = controls_spec(tmp_path)
    assert validate_spec(spec) == spec
    if mutation == "unknown":
        spec["private_extra"] = "ignored?"
    elif mutation == "bool":
        spec["budget"]["jobs"] = True
    elif mutation == "fee":
        spec["costs"]["crypto"] = [False, 10, 25]
    elif mutation == "duplicate":
        spec["arms"]["US"].append(spec["arms"]["US"][0])
    elif mutation == "arm":
        spec["arms"]["US"][0] = "best_after_seeing_results"
    elif mutation == "hash":
        spec["expected_input_hashes"]["US"] = "invalid"
    else:
        spec["role"] = "out_of_sample"
    with pytest.raises(ValueError, match="INVALID_CONTROLS_SPEC"):
        validate_spec(spec)


def test_duplicate_json_keys_are_rejected(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text('{"schema":"x","schema":"competition.strategy_controls_spec.v1"}')
    with pytest.raises(ValueError):
        load_spec(path)


def test_catalog_parameters_are_copies_and_unknown_arms_block():
    value = arm_spec("US", "ew_monthly_buffer20")
    assert value["parameters"]["buffer_l1"] == 0.20
    value["parameters"]["buffer_l1"] = 99
    assert arm_spec("US", "ew_monthly_buffer20")["parameters"]["buffer_l1"] == 0.20
    with pytest.raises(ValueError):
        arm_spec("US", "trend200_legacy")


def test_controls_help_does_not_read_configuration():
    child = subprocess.run(
        [sys.executable, "-m", "competition_tools.team", "controls", "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert child.returncode == 0, child.stderr
    assert "--spec" in child.stdout and "--output-root" in child.stdout


def test_spec_schema_matches_strict_contract(tmp_path):
    from jsonschema import Draft202012Validator

    schema_root = Path(__file__).resolve().parents[2] / "schemas/research"
    for name in ("spec", "plan", "job", "batch", "result", "periods"):
        schema = json.loads(
            (schema_root / f"strategy-controls-{name}.v1.schema.json").read_text()
        )
        Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(
        json.loads((schema_root / "strategy-controls-spec.v1.schema.json").read_text())
    )
    spec = controls_spec(tmp_path)
    validator.validate(spec)
    assert list(validator.iter_errors(spec | {"unknown": 1}))
