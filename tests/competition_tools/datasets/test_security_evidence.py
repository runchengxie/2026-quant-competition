import pytest

from competition_tools.datasets.security_evidence import audit_security_evidence


def fixtures():
    daily = [
        dict(
            date="2026-01-02",
            candidate_id="unresolved:A",
            ticker="A",
            open=100,
            close=101,
        ),
        dict(
            date="2026-01-05",
            candidate_id="unresolved:A",
            ticker="A",
            open=10,
            close=10.1,
        ),
    ]
    master = [dict(symbol="A", classification="unverified_security_type")]
    intervals = [
        dict(
            Ticker="A",
            ResearchKey="unresolved:A",
            first_date="2026-01-02",
            last_date="2026-01-05",
        )
    ]
    events = [
        dict(
            symbol="A",
            event_date="2026-01-05",
            event_type="forward_split",
            new_shares_per_old_share="10",
            apply_automatically="False",
        )
    ]
    return daily, master, intervals, events


def test_seed_event_does_not_certify_identity_or_adjust_raw_prices():
    data = fixtures()
    result = audit_security_evidence(*data)
    assert result["candidate_days"] == 2
    assert result["unresolved_candidate_days"] == 2
    assert result["source_seed_events"] == 1
    assert result["seed_split_boundary_matches"] == 1
    assert result["large_raw_boundary_jumps"] == 1
    assert result["unmatched_interval_days"] == 0
    assert result["formal_performance_ready"] is False
    assert result["prices_modified"] is False
    assert data[0][0]["close"] == 101


def test_missing_interval_is_visible_and_classification_is_not_inferred():
    daily, master, intervals, events = fixtures()
    result = audit_security_evidence(daily, master, [], events)
    assert result["unmatched_interval_days"] == 2
    assert result["independently_verified_type_days"] == 0


def test_overlap_duplicate_event_and_automatic_adjustment_are_rejected():
    daily, master, intervals, events = fixtures()
    with pytest.raises(ValueError):
        audit_security_evidence(daily, master, intervals * 2, events)
    with pytest.raises(ValueError):
        audit_security_evidence(daily, master, intervals, events * 2)
    events[0]["apply_automatically"] = "True"
    with pytest.raises(ValueError):
        audit_security_evidence(daily, master, intervals, events)
