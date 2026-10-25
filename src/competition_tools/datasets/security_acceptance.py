"""Audit explicit review attestations; a source URL alone proves no history."""

from datetime import date
from urllib.parse import urlsplit

CLAIMS = (
    "identity",
    "security_type",
    "corporate_actions",
    "price_basis",
    "availability",
)


def _day(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("INVALID_ACCEPTANCE_DATE")
    return value


def audit_pool(symbols, evidence, start, end):
    start, end = _day(start), _day(end)
    if (
        not isinstance(symbols, list)
        or not symbols
        or len(symbols) > 50
        or len(set(symbols)) != len(symbols)
        or any(
            not isinstance(s, str)
            or not s
            or not s.isascii()
            or not s.replace(".", "").isalnum()
            for s in symbols
        )
        or not isinstance(evidence, dict)
        or set(evidence) - set(symbols)
        or end < start
    ):
        raise ValueError("INVALID_ACCEPTANCE_POOL")
    rows = []
    for symbol in sorted(symbols):
        proof = evidence.get(symbol, {})
        if not isinstance(proof, dict) or set(proof) - set(CLAIMS) - {
            "start",
            "end",
            "sources",
        }:
            raise ValueError("UNKNOWN_ACCEPTANCE_FIELD")
        issues = [
            f"{key.upper()}_UNVERIFIED" for key in CLAIMS if proof.get(key) is not True
        ]
        sources = proof.get("sources", [])
        scope = (
            isinstance(sources, list)
            and bool(sources)
            and all(
                isinstance(s, str)
                and urlsplit(s).scheme == "https"
                and urlsplit(s).hostname
                and not urlsplit(s).username
                and not urlsplit(s).password
                for s in sources
            )
            and "start" in proof
            and "end" in proof
            and _day(proof["start"]) <= start <= end <= _day(proof["end"])
        )
        if not scope:
            issues.append("DATED_SOURCE_MISSING")
        rows.append(
            dict(
                symbol=symbol,
                status="review_attested" if not issues else "blocked",
                issue_codes=issues,
            )
        )
    return dict(
        schema="competition.security_acceptance.v1",
        start=start,
        end=end,
        requested=len(rows),
        accepted=[r["symbol"] for r in rows if not r["issue_codes"]],
        rows=rows,
        evidence_basis="explicit_review_attestation_only",
        provider_authenticity_verified=False,
        execution_authorized=False,
    )
