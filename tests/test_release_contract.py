import pytest

from packages.audit import validate_release_evidence


def valid_evidence():
    return {
        "run_id": "run-1",
        "strategy_id": "japanese-nira",
        "environment": "paper",
        "started_at": "2026-09-03T00:00:00Z",
        "events_file": "runs/run-1/events.jsonl",
    }


def test_release_evidence_requires_auditable_fields():
    with pytest.raises(ValueError, match="missing evidence"):
        validate_release_evidence({"run_id": "run-1"})


def test_release_evidence_rejects_credentials():
    evidence = valid_evidence()
    evidence["api_key"] = "never-store-this"
    with pytest.raises(ValueError, match="credentials"):
        validate_release_evidence(evidence)


def test_paper_release_cannot_claim_live_enabled():
    evidence = valid_evidence()
    evidence["live_enabled"] = True
    with pytest.raises(ValueError, match="paper"):
        validate_release_evidence(evidence)


def test_valid_paper_evidence_is_accepted():
    validate_release_evidence(valid_evidence())
