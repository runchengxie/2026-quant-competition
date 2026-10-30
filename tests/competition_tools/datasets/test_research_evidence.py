"""Byte verification is reproducible but cannot authenticate research evidence."""

import json
from pathlib import Path
import subprocess
import sys

import jsonschema
import pytest

from competition_tools.datasets.daily_storage import write_daily_manifest
from competition_tools.datasets.storage import digest, spec_hash, write_json
from test_daily_spec import daily_spec


BLOCKERS = (
    "POINT_IN_TIME_UNIVERSE_UNVERIFIED",
    "HISTORICAL_SECURITY_IDENTITY_UNVERIFIED",
    "CORPORATE_ACTION_COVERAGE_UNVERIFIED",
    "HISTORICAL_AVAILABILITY_UNVERIFIED",
    "OWNER_PROVENANCE_UNVERIFIED",
    "HOLDOUT_GOVERNANCE_UNVERIFIED",
)


@pytest.fixture
def snapshot(tmp_path):
    root = tmp_path / "dataset"
    root.mkdir()
    (root / ".dataset-owner").write_text("competition.dataset.v2")
    for folder in ("raw", "normalized"):
        (root / folder).mkdir()
        (root / folder / "AAPL.csv").write_text(
            "date,open,high,low,close,volume\n2024-07-01,1,2,1,2,3\n"
        )
    spec = daily_spec()
    receipt = dict(
        schema="competition.dataset_receipt.v2",
        spec_hash=spec_hash(spec),
        observed_at="2026-10-31T00:00:00Z",
        status="acquired",
        coverage={},
        gaps=[],
        issue_codes=[],
        resolved_contracts={},
        calendar={},
        adjustment_evidence={},
        requests=0,
        elapsed_seconds=0,
        parent_manifest_sha256=None,
        revisions=[],
        accepted_research=False,
        retained_payload_bytes=sum(p.stat().st_size for p in root.glob("*/*.csv")),
    )
    write_json(root / "receipt.json", receipt)
    write_daily_manifest(spec, root, receipt)
    return root / "manifest.json"


def audit(path, expected=None):
    from competition_tools.datasets.research_evidence import (
        audit_daily_research_evidence,
    )

    return audit_daily_research_evidence(path, expected or digest(path))


def test_report_is_closed_and_always_blocks_research(snapshot):
    value = audit(snapshot)
    schema = json.loads(
        (
            Path(__file__).parents[3]
            / "schemas/research/daily-research-evidence-gap.v1.schema.json"
        ).read_text()
    )
    jsonschema.Draft202012Validator(schema).validate(value)
    assert value["status"] == "blocked"
    assert value["accepted_research"] is False
    assert value["execution_authorized"] is False
    assert value["manifest_sha256"] == digest(snapshot)
    assert value["receipt_sha256"] == digest(snapshot.parent / "receipt.json")
    assert value["payload_files"] == 2
    assert value["checks"] == [
        dict(code="RETAINED_BYTES_VERIFIED", status="passed")
    ] + [dict(code=code, status="blocked") for code in BLOCKERS]
    assert str(snapshot.parent) not in json.dumps(value)
    for change in ({"extra": True}, {"accepted_research": True}, {"checks": []}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(schema).validate(value | change)


def test_hk_producer_supported_without_reading_connection(snapshot):
    value = json.loads(snapshot.read_text())
    spec = value["spec"]
    spec.update(
        market="HK", quote_currency="HKD", timezone="Asia/Hong_Kong", calendar="XHKG"
    )
    for contract in spec["contracts"]:
        contract.update(exchange="SEHK", currency="HKD")
    write_json(snapshot, value)
    assert audit(snapshot)["market"] == "HK"


@pytest.mark.parametrize(
    "kind", ["payload", "receipt", "extra_payload", "expected_hash"]
)
def test_integrity_failures(snapshot, kind):
    expected = digest(snapshot)
    if kind == "payload":
        (snapshot.parent / "raw/AAPL.csv").write_text("changed")
    elif kind == "receipt":
        write_json(snapshot.parent / "receipt.json", {})
    elif kind == "extra_payload":
        (snapshot.parent / "normalized/extra.csv").write_text("unrecorded")
    else:
        expected = "0" * 64
    with pytest.raises(ValueError):
        audit(snapshot, expected)


@pytest.mark.parametrize(
    "change",
    [
        {"schema": "other"},
        {"accepted_research": True},
        {"spec": {"source": "other"}},
        {"dataset_id": "other"},
        {"version": "other"},
        {"files": [True]},
    ],
)
def test_invalid_producer_or_structure(snapshot, change):
    write_json(snapshot, json.loads(snapshot.read_text()) | change)
    with pytest.raises(ValueError):
        audit(snapshot)


@pytest.mark.parametrize("file", ["manifest.json", "receipt.json"])
@pytest.mark.parametrize("body", ['{"x":1,"x":2}', '{"x":NaN}', "[]"])
def test_strict_json(snapshot, file, body):
    (snapshot.parent / file).write_text(body)
    with pytest.raises(ValueError):
        audit(snapshot)


def test_trust_assertions_cannot_upgrade(snapshot):
    value = json.loads(snapshot.read_text())
    value["spec"]["owner_verified"] = True
    write_json(snapshot, value)
    with pytest.raises(ValueError):
        audit(snapshot)


def test_mutation_during_verification_is_detected(snapshot, monkeypatch):
    from competition_tools.datasets import research_evidence as module

    original = module.verify_daily_manifest

    def mutate(path):
        value = original(path)
        (path.parent / "receipt.json").write_text("{}")
        return value

    monkeypatch.setattr(module, "verify_daily_manifest", mutate)
    with pytest.raises(ValueError, match="CHANGED"):
        audit(snapshot)


def test_cli_saves_new_report_but_never_overwrites(snapshot, tmp_path, capsys):
    from competition_tools.datasets.research_evidence import main

    output = tmp_path / "report.json"
    args = [
        "--manifest",
        str(snapshot),
        "--expected-sha256",
        digest(snapshot),
        "--output",
        str(output),
    ]
    assert main(args) == 0
    first = output.read_bytes()
    assert json.loads(first)["status"] == "blocked"
    assert main(args) == 2
    assert output.read_bytes() == first
    assert str(tmp_path) not in capsys.readouterr().out


@pytest.mark.parametrize("location", ["input", "source", "relative"])
def test_unsafe_output_rejected_before_verification(
    snapshot, tmp_path, monkeypatch, location
):
    from competition_tools.datasets import research_evidence as module

    outputs = {
        "input": snapshot.parent / "report.json",
        "source": tmp_path / "repo/report.json",
        "relative": Path("relative.json"),
    }
    (tmp_path / "repo/.git").mkdir(parents=True)

    def unexpected(*args):
        pytest.fail("Verification must not start for an invalid destination")

    monkeypatch.setattr(module, "audit_daily_research_evidence", unexpected)
    assert (
        module.main(
            [
                "--manifest",
                str(snapshot),
                "--expected-sha256",
                digest(snapshot),
                "--output",
                str(outputs[location]),
            ]
        )
        == 2
    )


def test_cli_error_is_sanitized_and_leaves_no_output(snapshot, tmp_path, capsys):
    from competition_tools.datasets.research_evidence import main

    output = tmp_path / "report.json"
    assert (
        main(
            [
                "--manifest",
                str(snapshot),
                "--expected-sha256",
                "bad",
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()
    assert str(tmp_path) not in capsys.readouterr().out


def test_symlink_input_rejected(snapshot, tmp_path):
    link = tmp_path / "linked.json"
    try:
        link.symlink_to(snapshot)
    except OSError:
        pytest.skip("OS does not permit symlink creation")
    with pytest.raises(ValueError):
        audit(link)


def test_finite_json_numeric_overflow_rejected(snapshot):
    body = snapshot.read_text().replace(
        '"coverage": {}', '"coverage": {"overflow": 1e999}'
    )
    snapshot.write_text(body)
    receipt = snapshot.parent / "receipt.json"
    receipt.write_text(
        receipt.read_text().replace('"coverage": {}', '"coverage": {"overflow": 1e999}')
    )
    with pytest.raises(ValueError, match="NONFINITE"):
        audit(snapshot)


def test_concurrent_output_winner_is_preserved(snapshot, tmp_path, monkeypatch):
    from competition_tools.datasets import research_evidence as module

    original = module.audit_daily_research_evidence
    output = tmp_path / "report.json"

    def concurrent(*args):
        result = original(*args)
        output.write_text("winner")
        return result

    monkeypatch.setattr(module, "audit_daily_research_evidence", concurrent)
    assert (
        module.main(
            [
                "--manifest",
                str(snapshot),
                "--expected-sha256",
                digest(snapshot),
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert output.read_text() == "winner"


def test_failed_publication_removes_only_its_output(snapshot, tmp_path, monkeypatch):
    from competition_tools.datasets import research_evidence as module

    output = tmp_path / "report.json"

    def fail(*args):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(module.os, "fsync", fail)
    assert (
        module.main(
            [
                "--manifest",
                str(snapshot),
                "--expected-sha256",
                digest(snapshot),
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()
    assert snapshot.exists()


def test_installed_dependencies_are_not_required(snapshot, tmp_path):
    source = Path(__file__).parents[3] / "src"
    output = tmp_path / "stdlib-report.json"
    code = (
        "import sys,runpy; sys.path.insert(0,sys.argv.pop(1)); "
        "runpy.run_module('competition_tools.datasets.research_evidence',run_name='__main__')"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-c",
            code,
            str(source),
            "--manifest",
            str(snapshot),
            "--expected-sha256",
            digest(snapshot),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text())["accepted_research"] is False


@pytest.mark.parametrize(
    "key,bad",
    [
        ("spec_hash", None),
        ("status", []),
        ("coverage", 1),
        ("gaps", {}),
        ("observed_at", "not-a-time"),
        ("observed_at", "2026-10-31T00:00:00"),
        ("parent_manifest_sha256", "wrong"),
    ],
)
def test_malformed_matching_producer_metadata_rejected(snapshot, key, bad):
    value = json.loads(snapshot.read_text())
    value[key] = bad
    value["receipt"][key] = bad
    write_json(snapshot.parent / "receipt.json", value["receipt"])
    write_json(snapshot, value)
    with pytest.raises(ValueError):
        audit(snapshot)


def test_conflicting_observation_time_rejected(snapshot):
    value = json.loads(snapshot.read_text())
    value["observed_at"] = "2026-10-30T00:00:00Z"
    write_json(snapshot, value)
    with pytest.raises(ValueError):
        audit(snapshot)
