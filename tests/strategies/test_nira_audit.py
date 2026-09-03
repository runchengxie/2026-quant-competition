from datetime import date

import pytest

from strategies.nira.audit import audit_forward_alignment


def test_forward_alignment_passes_when_returns_follow_signals():
    report = audit_forward_alignment(
        [date(2026, 1, 2), date(2026, 1, 5)],
        [date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)],
    )
    assert report.passed
    assert report.aligned_count == 2
    assert report.future_overlap_count == 0


def test_same_day_or_backward_join_is_flagged():
    report = audit_forward_alignment(["2026-01-05"], ["2026-01-04", "2026-01-05"])
    assert not report.passed
    assert report.future_overlap_count == 1


def test_horizon_must_be_positive():
    with pytest.raises(ValueError):
        audit_forward_alignment([], [], horizon=0)
