"""Selection precedes outcomes; proxy accounts retain unavailable dates."""

from datetime import date, timedelta

import pandas as pd
import pytest
import numpy as np

from equity_lab.predictive.comparison import (
    select_weights,
    score_account,
    training_slices,
)


def frame():
    return pd.DataFrame(
        [
            {
                "date": day,
                "candidate_id": name,
                "session_return": change,
                "price_valid": True,
            }
            for day, change in [
                ("2026-01-05", 0.0),
                ("2026-01-06", 0.1),
                ("2026-01-07", -0.1),
            ]
            for name in ["A", "B"]
        ]
    )


def test_ranking_ties_use_stable_identity_and_constant_rank_is_unavailable():
    assert select_weights(["B", "A", "C"], [2.0, 2.0, 1.0], top_n=1) == {"A": 1.0}
    with pytest.raises(ValueError, match="CONSTANT_SCORES"):
        select_weights(["A", "B"], [1.0, 1.0], top_n=1)
    with pytest.raises(ValueError):
        select_weights(["A", "B"], [float("nan"), 1.0], top_n=1)


def test_round_trip_cost_is_cash_funded_and_matches_price_minus_fees():
    raw = frame()
    raw.loc[
        (raw.date == "2026-01-06") & (raw.candidate_id == "B"), "session_return"
    ] = -0.1
    result = score_account(
        raw, None, ["2026-01-05"], sorted(raw.date.unique()), "equal_weight", 20, 0
    )
    assert result["status"] == "completed"
    fee = 20 / 10000
    assert result["metrics"]["net_return"] == pytest.approx((1 - fee) / (1 + fee) - 1)
    row = result["periods"][0]
    assert row["price_pnl"] - row["cost"] == pytest.approx(row["equity"] - 1)
    assert result["metrics"]["gross_return"] == pytest.approx(0)


def test_missing_next_session_is_not_replaced_by_the_next_observed_row():
    raw = frame()
    raw = raw[~((raw.date == "2026-01-06") & (raw.candidate_id == "A"))]
    dates = ["2026-01-05", "2026-01-06", "2026-01-07"]
    missing = score_account(raw, None, dates[:1], dates, "equal_weight", 0, 0)
    delayed = score_account(raw, None, dates[:1], dates, "equal_weight", 0, 1)
    assert missing["status"] == "blocked"
    assert missing["metrics"] is None
    assert missing["requested_dates"] == 1
    assert delayed["metrics"]["net_return"] == pytest.approx(-0.1)
    assert delayed["periods"][0]["execution_date"] == "2026-01-07"


def test_future_missing_labels_cannot_change_the_selected_portfolio():
    names = [f"C{i:02d}" for i in range(51)]
    raw = pd.DataFrame(
        [
            {
                "date": day,
                "candidate_id": name,
                "session_return": 0.1,
                "price_valid": True,
            }
            for day in ["2026-01-05", "2026-01-06"]
            for name in names
        ]
    )
    scores = pd.DataFrame(
        {"date": ["2026-01-05"] * 51, "candidate_id": names, "prediction": range(51)}
    )
    raw.loc[
        (raw.date == "2026-01-06") & (raw.candidate_id == "C50"), "session_return"
    ] = float("nan")
    result = score_account(
        raw, scores, ["2026-01-05"], ["2026-01-05", "2026-01-06"], "ridge", 0, 0
    )
    assert result["status"] == "blocked"
    assert result["periods"][0]["reason"] == "MISSING_SELECTED_OUTCOME"
    assert "C50" in result["periods"][0]["selected"]
    assert "C00" not in result["periods"][0]["selected"]


def test_constant_model_is_not_an_alphabetical_stock_picker():
    raw = frame()
    scores = raw[raw.date == "2026-01-05"][["date", "candidate_id"]].assign(
        prediction=0.0
    )
    result = score_account(
        raw, scores, ["2026-01-05"], sorted(raw.date.unique()), "elastic_net", 0, 0
    )
    assert result["status"] == "blocked"
    assert result["periods"][0]["reason"] == "CONSTANT_SCORES"


def test_concentration_diagnostic_is_explicit_and_does_not_modify_returns():
    days = pd.bdate_range("2026-01-05", periods=8).strftime("%Y-%m-%d").tolist()
    raw = pd.DataFrame(
        [
            dict(date=d, candidate_id="A", session_return=0.01, price_valid=True)
            for d in days
        ]
    )
    result = score_account(raw, None, days[:6], days, "equal_weight", 0, 0)
    assert result["metrics"]["net_return"] == pytest.approx(1.01**6 - 1)
    assert result["metrics"]["without_best_five_days_return"] == pytest.approx(0.01)
    assert result["metrics"]["top_asset_positive_price_pnl_share"] == pytest.approx(1)
    assert result["ex_post_diagnostic"] is True


def test_training_slices_purge_labels_at_the_boundary_and_ignore_future_targets():
    sessions = pd.bdate_range("2024-01-02", periods=190).strftime("%Y-%m-%d").tolist()
    raw = pd.DataFrame(
        dict(
            date=sessions,
            candidate_id=["A"] * 190,
            target=range(190),
            decision_at=pd.to_datetime([f"{day}T21:00Z" for day in sessions], utc=True),
            label_end=pd.to_datetime(
                [
                    f"{date.fromisoformat(day) + timedelta(days=1)}T21:00Z"
                    for day in sessions
                ],
                utc=True,
            ),
        )
    )
    dates = sessions[-20:]
    before = training_slices(raw, sessions, dates)
    changed = raw.copy()
    changed.loc[changed.date.isin(dates), "target"] = 1_000_000
    after = training_slices(changed, sessions, dates)
    for first, second in zip(before[:3], after[:3], strict=True):
        pd.testing.assert_frame_equal(first, second)
    assert (
        before[0].label_end < raw.loc[raw.date == dates[0], "decision_at"].iloc[0]
    ).all()


@pytest.mark.parametrize("fee, delay", [(True, 0), (20, True), (1000, 0), (20, 2)])
def test_unknown_or_boolean_cost_and_delay_are_rejected(fee, delay):
    raw = frame()
    with pytest.raises(ValueError):
        score_account(
            raw,
            None,
            ["2026-01-05"],
            sorted(raw.date.unique()),
            "equal_weight",
            fee,
            delay,
        )


def test_complete_synthetic_fit_pipeline_exports_unfiltered_scores_and_all_cells(
    tmp_path,
):
    pytest.importorskip(
        "sklearn", reason="Complete fitting requires the optional predictive profile"
    )
    from equity_lab.predictive.comparison import run_comparison

    sessions = pd.bdate_range("2024-01-02", periods=220).strftime("%Y-%m-%d").tolist()
    records = []
    for i, day in enumerate(sessions):
        for j in range(60):
            change = 0.003 * np.sin(j + i / 3)
            target = 0.003 * np.sin(j + (i + 1) / 3) if i < 219 else np.nan
            if i == 218 and j == 59:
                target = np.nan
            records.append(
                dict(
                    date=day,
                    candidate_id=f"DEMO{j:02d}",
                    ticker=f"DEMO{j:02d}",
                    decision_at=pd.Timestamp(f"{day}T21:00Z"),
                    label_end=pd.Timestamp(f"{sessions[min(i + 1, 219)]}T21:00Z"),
                    target=target,
                    session_return=np.nan if i == 219 and j == 59 else change,
                    range_fraction=abs(change) + 0.01,
                    relative_dollar_volume=1 + 0.01 * np.sin(i),
                    median_spread=0.001,
                    quote_fraction=0.99,
                    active_fraction=0.9,
                    dollar_volume=20_000_000.0,
                    close_price=100.0,
                    price_valid=not (i == 219 and j == 59),
                )
            )
    raw = pd.DataFrame(records)
    raw.attrs["sessions"] = sessions
    report = run_comparison(
        raw, sessions, tmp_path / "run", quality={"synthetic": True}
    )
    assert report["status"] == "completed"
    assert (tmp_path / "run/execution-observations.csv").is_file()
    assert (tmp_path / "run/decision-pool.csv").is_file()
    assert 36 <= report["fit_attempts"] <= 42
    assert len(report["accounts"]) == 72
    assert all(row["requested_dates"] == 20 for row in report["accounts"])
    paths = sorted((tmp_path / "run").glob("*-ridge-predictions.parquet"))
    assert len(paths) == 3
    last = pd.read_parquet(paths[-1])
    assert len(last) == 1200 and last.target.isna().sum() == 1
    assert last.prediction.notna().all()
    assert all(
        row["status"] == "blocked"
        for row in report["accounts"]
        if row["window"] == report["folds"][-1]["start"] and row["delay"] == 1
    )
