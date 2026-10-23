"""Real daily caches must not acquire execution readiness by assertion."""


import pytest

from competition_tools.datasets.storage import digest, write_json


def test_audit_preserves_real_data_blockers_without_pnl(tmp_path):
    from competition_tools.team.execution_readiness import audit_execution_inputs

    manifest = tmp_path / "manifest.json"
    write_json(
        manifest,
        dict(
            schema="competition.dataset_manifest.v2",
            spec=dict(market="US", quote_currency="USD", price_basis="split_adjusted"),
            receipt={},
        ),
    )
    value = audit_execution_inputs(
        dict(
            schema="competition.us_execution_readiness_spec.v1",
            manifests=[dict(path=str(manifest), sha256=digest(manifest))],
        )
    )
    assert value["status"] == "blocked"
    codes = {
        c["code"] for c in value["datasets"][0]["checks"] if c["status"] == "blocked"
    }
    assert {
        "RAW_EXECUTION_PRICES_REQUIRED",
        "CORPORATE_ACTION_MODEL_UNVERIFIED",
        "AVAILABILITY_EVIDENCE_UNVERIFIED",
    } <= codes
    assert "metrics" not in value
    assert value["orders_submitted"] == 0


def test_changed_manifest_is_not_audited_as_original(tmp_path):
    from competition_tools.team.execution_readiness import audit_execution_inputs

    manifest = tmp_path / "manifest.json"
    write_json(manifest, {})
    spec = dict(
        schema="competition.us_execution_readiness_spec.v1",
        manifests=[dict(path=str(manifest), sha256=digest(manifest))],
    )
    write_json(manifest, {"changed": True})
    with pytest.raises(ValueError, match="HASH"):
        audit_execution_inputs(spec)


def test_readiness_help_needs_no_configuration(capsys):
    from competition_tools.team.__main__ import main

    with pytest.raises(SystemExit) as exc:
        main(["execution-readiness", "--help"])
    assert exc.value.code == 0
    assert "--spec" in capsys.readouterr().out
