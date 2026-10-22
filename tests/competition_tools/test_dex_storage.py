import json

import pytest
from jsonschema import Draft202012Validator
from pathlib import Path

from competition_tools.datasets.dex_acquisition import acquire_dex, resume_state
from competition_tools.datasets.dex_storage import publish_dex, verify_dex_manifest
from competition_tools.datasets.dex_transport import DexTransport
from test_dex_acquisition import case


def test_concurrent_staging_lock_never_broken(tmp_path):
    spec, staging, transport, _ = case(tmp_path)
    staging.mkdir()
    (staging / ".dataset-owner").write_text("competition.dex_dataset.v1")
    (staging / ".acquiring").write_text("busy")
    with pytest.raises(ValueError):
        acquire_dex(spec, staging, transport=transport)
    assert (staging / ".acquiring").read_text() == "busy"
    assert transport.requests == 0


def test_interrupted_unknown_spend_and_corrupt_resume_rejected(tmp_path):
    spec, staging, transport, _ = case(tmp_path, substitution=True)
    acquire_dex(spec, staging, transport=transport)
    prior = resume_state(spec, staging)
    assert prior["spent"]["requests"] == transport.requests
    with (staging / "requests-1.jsonl").open("a") as stream:
        stream.write('{"status":"interrupted"}\n')
    with pytest.raises(ValueError, match="RESUME_HASH_OR_BUDGET_MISMATCH"):
        resume_state(spec, staging)


def test_changed_spec_resume_rejected(tmp_path):
    spec, staging, transport, _ = case(tmp_path, substitution=True)
    acquire_dex(spec, staging, transport=transport)
    spec["version"] = "v2"
    with pytest.raises(ValueError, match="CHANGED_DEX_SPEC"):
        resume_state(spec, staging)


def test_corrupt_retained_response_blocks_resume(tmp_path):
    spec, staging, transport, _ = case(tmp_path, substitution=True)
    acquire_dex(spec, staging, transport=transport)
    (staging / "raw/networks.json").write_text("[]")
    with pytest.raises(ValueError, match="RESUME_HASH_OR_BUDGET_MISMATCH"):
        resume_state(spec, staging)


def test_unlisted_file_and_reparse_block_inspection(tmp_path):
    spec, staging, transport, _ = case(tmp_path)
    acquire_dex(spec, staging, transport=transport)
    (staging / "unexpected.json").write_text("{}")
    with pytest.raises(ValueError, match="UNLISTED_DATASET_FILE"):
        verify_dex_manifest(staging / "manifest.json")
    (staging / "unexpected.json").unlink()
    link = staging / "linked.json"
    link.symlink_to(staging / "raw/networks.json")
    with pytest.raises(ValueError, match="DEX_REPARSE_PATH"):
        verify_dex_manifest(staging / "manifest.json")


def test_forged_manifest_status_is_rejected(tmp_path):
    spec, staging, transport, _ = case(tmp_path)
    acquire_dex(spec, staging, transport=transport)
    path = staging / "manifest.json"
    value = json.loads(path.read_text())
    value["status"] = "made_up"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="INVALID_DEX_MANIFEST"):
        verify_dex_manifest(path)


def test_resume_cannot_reset_cumulative_budget(tmp_path):
    spec, staging, transport, _ = case(tmp_path, substitution=True)
    acquire_dex(spec, staging, transport=transport)
    new = DexTransport(
        spec["budget"], Path(spec["credential_file"]), staging / "requests-2.jsonl"
    )
    with pytest.raises(ValueError, match="RESUME_BUDGET_NOT_REDUCED"):
        acquire_dex(spec, staging, transport=new)
    assert new.requests == 0


def test_publication_interruption_preserves_owned_staging(tmp_path, monkeypatch):
    spec, staging, transport, _ = case(tmp_path)
    acquire_dex(spec, staging, transport=transport)
    original = Path.rename

    def denied(self, target):
        if self == staging:
            raise OSError("fixture interruption")
        return original(self, target)

    monkeypatch.setattr(Path, "rename", denied)
    with pytest.raises(OSError):
        publish_dex(staging, tmp_path / "destination")
    assert verify_dex_manifest(staging / "manifest.json")
    assert not (tmp_path / "destination.publish-lock").exists()


def test_artifacts_match_exact_schemas(tmp_path):
    spec, staging, transport, _ = case(tmp_path)
    receipt = acquire_dex(spec, staging, transport=transport)
    root = Path(__file__).resolve().parents[2] / "schemas/research"
    for name, value in [
        ("dex-dataset-receipt.v1", receipt),
        ("dex-dataset-manifest.v1", verify_dex_manifest(staging / "manifest.json")),
    ]:
        schema = json.loads((root / (name + ".schema.json")).read_text())
        validator = Draft202012Validator(schema)
        validator.validate(value)
