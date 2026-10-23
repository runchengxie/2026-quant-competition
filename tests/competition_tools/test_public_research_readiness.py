"""Status summaries must exclude private receipts and unsupported capabilities."""

import copy
import pytest


def public_fixture():
    return dict(
        schema="competition.public_strategy_evidence_readiness.v1",
        as_of="2026-10-23T12:00:00Z",
        code_commit="a" * 40,
        execution=dict(
            status="blocked",
            model_id="us-next-session-price-nav.v1",
            datasets_checked=2,
            blockers=["CORPORATE_ACTION_MODEL_UNVERIFIED"],
            return_basis="usd_price_nav",
            orders_submitted=0,
            total_return=False,
            execution_eligible=False,
            receipt_sha256="b" * 64,
        ),
        observation=dict(
            schema="competition.observation_status.v1",
            protocol_id="c" * 64,
            status="awaiting_new_data",
            freeze_at="2026-10-23T10:00:00Z",
            first_eligible_observation_at=None,
            observations=0,
            evidence_tier="readiness_only",
            execution_authorized=False,
        ),
    )


def test_public_readiness_has_no_private_or_invented_facts():
    from competition_tools.evaluation.research_readiness import (
        validate_public_readiness,
    )

    source = public_fixture()
    assert validate_public_readiness(source) == source
    for mutate in (
        lambda x: x["execution"].update(account="private"),
        lambda x: x["execution"].update(orders_submitted=True),
        lambda x: x["observation"].update(observations=1),
        lambda x: x["observation"].update(execution_authorized=True),
    ):
        value = copy.deepcopy(source)
        mutate(value)
        with pytest.raises(ValueError):
            validate_public_readiness(value)
