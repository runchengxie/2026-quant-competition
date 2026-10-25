"""Dated evidence gates must not promote current symbols into trusted history."""

import pytest

from competition_tools.datasets.security_acceptance import audit_pool


def evidence():
    return {
        "identity": True,
        "security_type": True,
        "corporate_actions": True,
        "price_basis": True,
        "availability": True,
        "start": "2025-01-01",
        "end": "2026-10-20",
        "sources": ["https://www.sec.gov/Archives/example"],
    }


def test_no_evidence_never_accepts_an_existing_symbol():
    result = audit_pool(["AAPL", "MSFT"], {}, "2025-09-25", "2026-10-20")
    assert result["accepted"] == []
    assert result["requested"] == 2
    assert result["rows"][0]["issue_codes"] == [
        "IDENTITY_UNVERIFIED",
        "SECURITY_TYPE_UNVERIFIED",
        "CORPORATE_ACTIONS_UNVERIFIED",
        "PRICE_BASIS_UNVERIFIED",
        "AVAILABILITY_UNVERIFIED",
        "DATED_SOURCE_MISSING",
    ]


def test_acceptance_requires_all_five_claims_and_full_dated_scope():
    proof = evidence()
    assert audit_pool(["AAPL"], {"AAPL": proof}, "2025-09-25", "2026-10-20")[
        "accepted"
    ] == ["AAPL"]
    proof["end"] = "2026-10-19"
    assert (
        audit_pool(["AAPL"], {"AAPL": proof}, "2025-09-25", "2026-10-20")["accepted"]
        == []
    )
    proof = evidence() | {"identity": "true"}
    assert (
        "IDENTITY_UNVERIFIED"
        in audit_pool(["AAPL"], {"AAPL": proof}, "2025-09-25", "2026-10-20")["rows"][0][
            "issue_codes"
        ]
    )


def test_duplicate_or_unknown_evidence_is_rejected():
    with pytest.raises(ValueError):
        audit_pool(["AAPL", "AAPL"], {}, "2025-09-25", "2026-10-20")
    with pytest.raises(ValueError):
        audit_pool(
            ["AAPL"],
            {"AAPL": evidence() | {"private_account": "x"}},
            "2025-09-25",
            "2026-10-20",
        )
