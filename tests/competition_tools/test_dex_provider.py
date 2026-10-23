from datetime import datetime, timezone

import pytest

from competition_tools.datasets.dex_provider import (
    plan_dex,
    usage_preflight,
    require_headroom,
)
from test_dex_spec import sample


class Transport:
    requests = 1
    utc_now = staticmethod(lambda: datetime(2026, 10, 22, tzinfo=timezone.utc))

    def __init__(self, value):
        self.value = value
        self.credit_state = None

    def get_json(self, endpoint):
        assert endpoint == "usage"
        return self.value


def usage(**changes):
    return (
        dict(
            plan="pro",
            email="private@example.invalid",
            requests_used=20,
            requests_left=4999980,
            period_started_at="2026-10-01T00:00:00Z",
            period_ends_at="2026-11-01T00:00:00Z",
        )
        | changes
    )


def test_usage_excludes_identity_and_overage():
    result = usage_preflight(Transport(usage(requests_left=9000000)), 98)
    assert result["status"] == "allowed"
    assert result["included_remaining"] == 4999980
    assert result["credit_upper_bound_per_attempt"] == 1
    assert "email" not in result


@pytest.mark.parametrize(
    "changes",
    [
        {"plan": "unknown"},
        {"requests_used": True},
        {"requests_left": -1},
        {"requests_used": 4999990},
        {"requests_left": 1},
        {"period_ends_at": "bad"},
    ],
)
def test_unverified_or_exhausted_usage_blocks(changes):
    assert usage_preflight(Transport(usage(**changes)), 98)["status"] == "blocked"


@pytest.mark.parametrize(
    "changes",
    [
        {"period_started_at": "2026-10-02T00:00:00Z"},
        {"requests_used": 19},
    ],
)
def test_changed_period_or_usage_discontinuity_blocks(changes):
    transport = Transport(usage())
    assert usage_preflight(transport, 98)["status"] == "allowed"
    transport.value = usage(**changes)
    assert usage_preflight(transport, 98)["status"] == "blocked"


def test_plan_is_offline_and_stable(tmp_path):
    spec = sample(tmp_path)
    result = plan_dex(spec)
    assert result == plan_dex(spec)
    assert result["ohlcv_requests"] == 3
    assert result["worst_case_attempts"] <= spec["budget"]["requests"]
    assert "credential_file" not in str(result)
    assert result["unresolved"]


def test_remaining_batch_is_reserved_locally():
    transport = Transport(usage(requests_used=4999900, requests_left=100))
    assert usage_preflight(transport, 98)["status"] == "allowed"
    transport.requests += 3
    with pytest.raises(ValueError, match="INCLUDED_CREDITS_EXHAUSTED"):
        require_headroom(transport, 98)


def test_expired_usage_period_is_checked_against_injected_clock():
    from datetime import datetime, timezone

    transport = Transport(usage())
    transport.utc_now = lambda: datetime(2030, 1, 1, tzinfo=timezone.utc)
    assert usage_preflight(transport, 98)["status"] == "blocked"
