"""A separate sixty-session validation policy preserves the earlier protocol."""

import pytest

from equity_lab.predictive.comparison import training_slices
from equity_lab.predictive.holding_data import prepare_holding
from test_predictive_holding import raw_fixture


def test_sixty_session_validation_keeps_twenty_day_labels_before_boundary():
    raw, schedule = raw_fixture(270, 2)
    frame = prepare_holding(raw, schedule, 20)
    sessions = frame.attrs["sessions"]
    dates = sessions[-101:-61]
    outer, train, valid, requested = training_slices(
        frame, sessions, dates, validation_sessions=60
    )
    assert len(requested) == 60
    assert valid.date.nunique() == 40
    assert (
        train.label_end.max()
        < frame.loc[frame.date == requested[0], "decision_at"].iloc[0]
    )
    assert (
        outer.label_end.max() < frame.loc[frame.date == dates[0], "decision_at"].iloc[0]
    )
    legacy = training_slices(frame, sessions, dates)
    assert len(legacy[-1]) == 34


def test_sixty_session_policy_requires_eighty_inner_calendar_sessions():
    raw, schedule = raw_fixture(230, 2)
    frame = prepare_holding(raw, schedule, 20)
    sessions = frame.attrs["sessions"]
    with pytest.raises(ValueError, match="INNER_TRAINING_CALENDAR"):
        training_slices(frame, sessions, sessions[-101:-61], validation_sessions=60)
    with pytest.raises(ValueError):
        training_slices(frame, sessions, sessions[-101:-61], validation_sessions=True)


def test_new_profile_exports_complete_validation_scope(tmp_path):
    pytest.importorskip("sklearn")
    from equity_lab.predictive.holding import run_holding

    raw, schedule = raw_fixture(270)
    report = run_holding(raw, schedule, tmp_path / "extended", profile="validation60")
    assert report["schema"] == "equity.low_turnover_ml.v2"
    assert report["validation_sessions"] == 60
    assert len(report["accounts"]) == 168
    assert 48 <= report["fit_attempts"] <= 56
    for model in report["models"]:
        for candidate in model["candidates"]:
            if candidate["status"] == "completed":
                assert candidate["metrics"]["requested_dates"] == 60
                assert candidate["metrics"]["valid_mse_dates"] >= 40
                # A constant fitted predictor has valid labels but no rank IC.
                assert (
                    0
                    <= candidate["metrics"]["valid_ic_dates"]
                    <= candidate["metrics"]["valid_mse_dates"]
                )
