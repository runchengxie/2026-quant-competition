import json

import numpy as np
import pandas as pd
import pytest

from equity_lab.predictive.protocol import (
    Budget,
    daily_metrics,
    outer_blocks,
    select_candidate,
    split_training,
)


def test_calendar_blocks_do_not_move_for_missing_labels():
    dates = pd.bdate_range("2025-01-01", periods=200).strftime("%Y-%m-%d").tolist()
    blocks = outer_blocks(dates)
    assert len(blocks) == 3
    assert blocks[0] == dates[140:160]
    assert blocks[-1] == dates[180:200]
    with pytest.raises(ValueError, match="126"):
        outer_blocks(dates[:185])


def test_purge_by_label_end_strictly_before_decision():
    frame = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-01-05"],
            "label_end": pd.to_datetime(
                ["2026-01-02T21:00Z", "2026-01-05T21:00Z", "2026-01-06T21:00Z"]
            ),
        }
    )
    result = split_training(frame, "2026-01-05", pd.Timestamp("2026-01-05T21:00Z"))
    assert result.date.tolist() == ["2026-01-01"]


def test_daily_ic_requires_distinct_ids_and_nonconstant_scores():
    frame = pd.DataFrame(
        {
            "date": ["2026-01-01"] * 30,
            "candidate_id": [str(i) for i in range(30)],
            "target": np.arange(30) / 100,
        }
    )
    good = daily_metrics(frame, np.arange(30) / 100, ["2026-01-01", "2026-01-02"])
    assert good["valid_ic_dates"] == 1
    assert good["requested_dates"] == 2
    assert good["mean_daily_ic"] == pytest.approx(1)
    constant = daily_metrics(frame, np.zeros(30), ["2026-01-01"])
    assert constant["mean_daily_ic"] is None
    assert constant["daily"][0]["ic_reason"] == "constant_scores_or_labels"
    frame["candidate_id"] = "same"
    with pytest.raises(ValueError, match="Duplicate"):
        daily_metrics(frame, np.arange(30), ["2026-01-01"])


def test_selection_has_no_mse_fallback_and_deterministic_ties():
    rows = [
        {
            "params": {"alpha": 1},
            "status": "completed",
            "metrics": {
                "valid_ic_dates": 19,
                "mean_daily_ic": 0.9,
                "mean_daily_mse": 0.01,
            },
        },
        {
            "params": {"alpha": 10},
            "status": "completed",
            "metrics": {
                "valid_ic_dates": 20,
                "mean_daily_ic": 0.1,
                "mean_daily_mse": 0.02,
            },
        },
        {
            "params": {"alpha": 0.1},
            "status": "completed",
            "metrics": {
                "valid_ic_dates": 20,
                "mean_daily_ic": 0.1,
                "mean_daily_mse": 0.01,
            },
        },
    ]
    assert select_candidate(rows)["params"] == {"alpha": 0.1}
    assert select_candidate(rows[:1]) is None


def test_budget_persists_attempt_before_fit_and_refuses_retry(tmp_path):
    clock = [0.0]
    budget = Budget(
        tmp_path / "attempts.jsonl", max_attempts=2, seconds=1, clock=lambda: clock[0]
    )
    budget.begin({"model": "ridge"})
    budget.begin({"model": "elastic_net"})
    with pytest.raises(RuntimeError, match="budget"):
        budget.begin({})
    assert len((tmp_path / "attempts.jsonl").read_text().splitlines()) == 2
    assert (
        json.loads((tmp_path / "attempts.jsonl").read_text().splitlines()[0])["attempt"]
        == 1
    )
    other = Budget(tmp_path / "other.jsonl", clock=lambda: clock[0], seconds=1)
    clock[0] = 2
    with pytest.raises(RuntimeError, match="budget"):
        other.begin({})


def test_optional_model_pipeline_fits_transformations_on_training_only():
    pytest.importorskip("sklearn")
    from equity_lab.predictive.protocol import fit_model

    train = np.array([[0.0, 1.0], [2.0, np.nan], [4.0, 3.0]])
    model = fit_model("ridge", {"alpha": 1}, train, np.array([0.0, 1.0, 2.0]))
    assert model.named_steps["scale"].mean_[0] == 2
    assert np.isfinite(model.predict(np.array([[1000.0, np.nan]]))).all()


def test_solver_warning_is_a_failed_fit(monkeypatch):
    pytest.importorskip("sklearn")
    import warnings
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import ElasticNet
    from equity_lab.predictive.protocol import fit_model

    def warn(self, x, y, **kwargs):
        warnings.warn("solver did not converge", ConvergenceWarning)
        return self

    monkeypatch.setattr(ElasticNet, "fit", warn)
    with pytest.raises(ConvergenceWarning):
        fit_model(
            "elastic_net",
            {"alpha": 0.001, "l1_ratio": 0.5},
            np.array([[0.0], [1.0]]),
            np.array([0.0, 1.0]),
        )


def test_failed_model_candidates_leave_complete_receipts(tmp_path):
    pytest.importorskip("sklearn")
    from equity_lab.predictive.data import FEATURES
    from equity_lab.predictive.protocol import run_pilot

    sessions = pd.bdate_range("2025-01-01", periods=200).strftime("%Y-%m-%d").tolist()
    rows = []
    for i, date in enumerate(sessions):
        decision = pd.Timestamp(date + "T21:00:00Z")
        end = (
            pd.Timestamp(sessions[i + 1] + "T21:00:00Z")
            if i + 1 < len(sessions)
            else pd.NaT
        )
        rows.append(
            {
                "date": date,
                "candidate_id": "unresolved:A",
                "ticker": "A",
                "decision_at": decision,
                "label_end": end,
                "target": 0.0,
                "price_valid": True,
                "close_price": 10.0,
                "dollar_volume": 20_000_000.0,
                **dict.fromkeys(FEATURES, 0.0),
            }
        )
    frame = pd.DataFrame(rows)
    frame.attrs["sessions"] = sessions
    output = tmp_path / "failed-experiment"
    report = run_pilot(frame, sessions, output, "exploratory_source_candidates")
    assert report["status"] == "completed_with_failures"
    assert report["fit_attempts"] == 36
    assert all(
        c["status"] == "failed" for f in report["folds"] for c in f["candidates"]
    )
    assert all(
        m["status"] == "unselectable" for f in report["folds"] for m in f["models"]
    )
    assert len((output / "attempts.jsonl").read_text().splitlines()) == 36
    assert (
        json.loads((output / "report.json").read_text())["status"]
        == "completed_with_failures"
    )
