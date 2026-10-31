"""Separate frozen forest family; tests never fit retained market inputs."""

import numpy as np
import pytest

from equity_lab.predictive.forest_profile import parameters, build_model
from equity_lab.predictive.forest_study import run_forest_study


def test_exact_four_settings_and_explicit_defaults():
    pytest.importorskip("sklearn")
    for kind in ("random_forest", "extra_trees"):
        for depth in (3, 5):
            params = parameters(kind, depth)
            assert params["n_estimators"] == 100
            assert params["n_jobs"] == 2
            assert params["max_depth"] == depth
            assert params["bootstrap"] is (kind == "random_forest")
            assert (
                build_model(kind, {"max_depth": depth})["model"].get_params() == params
            )
    with pytest.raises(ValueError):
        parameters("random_forest", 4)


def test_training_only_median_and_constant_empty_feature():
    pytest.importorskip("sklearn")
    model = build_model("extra_trees", {"max_depth": 3})
    imputer = model["impute"]
    train = np.array([[1.0, np.nan], [3.0, np.nan]])
    imputer.fit(train)
    np.testing.assert_array_equal(imputer.transform([[np.nan, 100.0]]), [[2.0, 100.0]])
    np.testing.assert_array_equal(imputer.statistics_, [2.0, 0.0])


def test_default_api_requires_owner_claim_before_reading_input(tmp_path):
    with pytest.raises(ValueError, match="FOREST_HORIZON_CLAIM_REQUIRED"):
        run_forest_study(None, None, tmp_path / "output", {})


def test_real_default_rejects_synthetic_input_before_any_fit(tmp_path, monkeypatch):
    from equity_lab.predictive import forest_study_guard
    from equity_lab.predictive.forest_profile import require_real_input

    monkeypatch.setattr(
        forest_study_guard, "validate_claim", lambda *args: tmp_path / "ledger"
    )
    with pytest.raises(ValueError, match="FOREST_RETAINED_INPUT_REQUIRED"):
        run_forest_study(
            None, None, tmp_path / "output", {"input_sha256": "0" * 64}, claim={}
        )
    with pytest.raises(ValueError, match="FOREST_RETAINED_INPUT_REQUIRED"):
        require_real_input({})
    assert not (tmp_path / "output").exists()


def test_forest_budget_hard_caps_caller_requested_limit(tmp_path):
    from equity_lab.predictive.forest_study import StudyBudget

    budget = StudyBudget(tmp_path / "starts.jsonl", max_attempts=99)
    for index in range(12):
        budget.begin(dict(synthetic=index))
    with pytest.raises(RuntimeError, match="budget exhausted"):
        budget.begin(dict(synthetic=12))
    with pytest.raises(FileExistsError):
        StudyBudget(tmp_path / "starts.jsonl")


def test_predictions_include_full_grid_when_future_labels_missing(tmp_path):
    from test_forest_guard import frames
    from equity_lab.predictive.forest_study import fit_block, StudyBudget

    frame, dates = frames()
    test = frame.copy()
    test.loc[test.date == dates[-1], "target"] = np.nan

    class Linear:
        def predict(self, x):
            return x[:, 0]

    result, predictions = fit_block(
        frame,
        frame,
        frame,
        test,
        dates,
        StudyBudget(tmp_path / "starts.jsonl"),
        20,
        dates[0],
        kind="extra_trees",
        fit=lambda *args: Linear(),
    )
    assert result["status"] == "completed"
    assert len(predictions) == len(test)
    assert predictions.prediction.notna().all()
    assert result["metrics"]["daily"][-1]["count"] == 0


def test_shared_forest_training_slices_purge_calendar_label_ends():
    import pandas as pd
    from test_predictive_holding import raw_fixture
    from equity_lab.predictive.data import FEATURES
    from equity_lab.predictive.comparison import training_slices
    from equity_lab.predictive.holding_data import prepare_holding, holding_folds

    raw, schedule = raw_fixture(260, 3)
    frame = prepare_holding(raw, schedule, 20)
    sessions = frame.attrs["sessions"]
    dates = holding_folds(sessions)[0]
    outer, train, valid, validation = training_slices(
        frame, sessions, dates, validation_sessions=60
    )
    decision = frame.loc[frame.date == dates[0], "decision_at"].iloc[0]
    inner_decision = frame.loc[frame.date == validation[0], "decision_at"].iloc[0]
    assert len(validation) == 60
    assert sessions.index(validation[0]) >= 80
    assert (outer.label_end < decision).all()
    assert (train.label_end < inner_decision).all()
    assert (train.date < validation[0]).all()
    assert valid.date.isin(validation).all()
    changed = raw.copy()
    future = changed.TradeDate >= pd.Timestamp(dates[0])
    changed.loc[future, "close_price"] *= 100
    altered = prepare_holding(changed, schedule, 20)
    other, inner, _, _ = training_slices(
        altered, sessions, dates, validation_sessions=60
    )
    pd.testing.assert_frame_equal(
        outer[FEATURES + ["target"]], other[FEATURES + ["target"]]
    )
    pd.testing.assert_frame_equal(
        train[FEATURES + ["target"]], inner[FEATURES + ["target"]]
    )
