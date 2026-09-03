import pytest

from strategies.nira.audit import audit_feature_cutoff


def test_feature_cutoff_requires_features_before_signal_and_label_after_signal():
    report = audit_feature_cutoff(
        ["2026-01-05"], ["2026-01-04"], ["2026-01-06"]
    )
    assert report.passed is True


def test_feature_or_label_timing_violation_is_reported():
    report = audit_feature_cutoff(
        ["2026-01-05", "2026-01-06"], ["2026-01-06", "2026-01-05"], ["2026-01-05", "2026-01-07"]
    )
    assert report.passed is False
    assert report.feature_after_signal_count == 1
    assert report.label_not_after_signal_count == 1


def test_cutoff_audit_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        audit_feature_cutoff(["2026-01-01"], [], ["2026-01-02"])
