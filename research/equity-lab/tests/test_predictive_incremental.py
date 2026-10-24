from datetime import timedelta

import numpy as np
import pandas as pd
import pytest


def test_reversal_preserves_ties_and_does_not_claim_score_mse():
    from equity_lab.predictive.incremental import score_metrics

    frame = pd.DataFrame(
        {
            "date": ["2026-08-03"] * 30,
            "candidate_id": list(map(str, range(30))),
            "target": np.repeat(np.arange(15), 2),
        }
    )
    metric = score_metrics(
        frame, -frame.target.to_numpy(), ["2026-08-03"], ranking=True
    )
    assert metric["mean_daily_ic"] == pytest.approx(-1)
    assert metric["mean_daily_mse"] is None
    assert metric["daily"][0]["mse"] is None


def test_feature_ablation_grid_has_45_planned_fits():
    from equity_lab.predictive.incremental import model_specs

    specs = model_specs()
    assert sum(len(s["grid"]) + 1 for s in specs) * 3 == 45
    assert specs[1]["features"] == ["session_return"]
    assert "session_return" not in specs[2]["features"]


def test_tree_fits_without_random_early_stopping_and_train_imputation():
    pytest.importorskip("sklearn")
    from equity_lab.predictive.incremental import fit_incremental

    x = np.column_stack([np.linspace(-1, 1, 240), np.full(240, np.nan)])
    y = x[:, 0] ** 2
    model = fit_incremental("tree", {"max_depth": 2}, x, y)
    assert model.named_steps["model"].early_stopping is False
    assert model.named_steps["model"].n_iter_ == 100
    assert len(model.predict([[100, np.nan]])) == 1
    assert model.named_steps["impute"].statistics_[0] == pytest.approx(0)


def test_strata_keep_invalid_and_small_cells_visible():
    from equity_lab.predictive.incremental import descriptive_metrics

    frame = pd.DataFrame(
        {
            "date": ["2026-08-03"] * 90,
            "candidate_id": list(map(str, range(90))),
            "target": np.arange(90),
            "prior_dollar_volume": np.arange(90) + 1,
            "median_spread": [np.nan] * 90,
        }
    )
    facts = descriptive_metrics(frame, np.arange(90), ["2026-08-03"])
    assert facts["liquidity"]["low"]["daily"][0]["count"] == 30
    assert facts["liquidity"]["high"]["mean_daily_ic"] == pytest.approx(1)
    assert facts["spread"]["low"]["mean_daily_ic"] is None
    assert facts["spread"]["missing"]["daily"][0]["count"] == 90


def test_fixed_protocol_keeps_three_calendars_shared_rows_and_45_attempts(tmp_path):
    pytest.importorskip("sklearn")
    from equity_lab.predictive.data import FEATURES
    from equity_lab.predictive.incremental import run_incremental

    dates = pd.bdate_range("2025-01-01", periods=210).strftime("%Y-%m-%d").tolist()
    rng = np.random.default_rng(17)
    rows = []
    for index, day in enumerate(dates):
        decision = pd.Timestamp(f"{day}T21:00:00Z")
        for identity in range(30):
            features = dict(zip(FEATURES, rng.normal(size=6)))
            rows.append(
                dict(
                    features,
                    date=day,
                    candidate_id=str(identity),
                    ticker=str(identity),
                    target=-features["session_return"] + rng.normal(scale=0.1),
                    decision_at=decision,
                    label_end=pd.Timestamp(
                        decision.to_pydatetime() + timedelta(days=1)
                    ),
                    dollar_volume=20_000_000,
                    price_valid=True,
                    close_price=10,
                    prior_dollar_volume=20_000_000,
                )
            )
    frame = pd.DataFrame(rows)
    frame.attrs["sessions"] = dates
    report = run_incremental(frame, dates, tmp_path / "run")
    assert report["status"] == "completed"
    assert report["fit_attempts"] == 45
    assert [f["start"] for f in report["folds"]] == [dates[-60], dates[-40], dates[-20]]
    for fold in report["folds"]:
        assert {m["metrics"]["requested_dates"] for m in fold["models"]} == {20}
        assert all(
            r["count"] == r["reference_count"]
            for m in fold["models"]
            for r in m["versus_reversal"]["daily"]
        )
    assert len(list((tmp_path / "run").glob("*-predictions.parquet"))) == 12


def test_strata_cutpoints_do_not_depend_on_future_label_availability():
    from equity_lab.predictive.incremental import descriptive_metrics

    universe = pd.DataFrame(
        {
            "date": ["2026-08-03"] * 90,
            "candidate_id": list(map(str, range(90))),
            "target": np.arange(90),
            "prior_dollar_volume": np.arange(90) + 1,
            "median_spread": np.arange(90) / 1000,
        }
    )
    scored = universe.iloc[30:]
    result = descriptive_metrics(
        scored, np.arange(60), ["2026-08-03"], eligible=universe
    )
    assert result["liquidity"]["low"]["daily"][0]["count"] == 0
    assert result["liquidity"]["middle"]["daily"][0]["count"] == 30
    assert result["liquidity"]["high"]["daily"][0]["count"] == 30


@pytest.mark.parametrize("missing", [1, 40])
def test_missing_predictions_keep_eligible_coverage_and_disable_daily_comparison(
    missing,
):
    from equity_lab.predictive.incremental import score_metrics, paired_metrics

    frame = pd.DataFrame(
        {
            "date": ["2026-08-03"] * 40,
            "candidate_id": list(map(str, range(40))),
            "target": np.arange(40),
        }
    )
    prediction = np.arange(40, dtype=float)
    prediction[:missing] = np.nan
    metric = score_metrics(frame, prediction, ["2026-08-03"])
    reference = score_metrics(frame, np.arange(40), ["2026-08-03"])
    assert metric["daily"][0]["count"] == 40
    assert metric["daily"][0]["rank_ic"] is None
    assert metric["daily"][0]["ic_reason"] == "missing_predictions"
    assert metric["valid_mse_dates"] == 0
    paired = paired_metrics(metric, reference)
    assert paired["valid_dates"] == 0
    assert paired["daily"][0]["difference"] is None


def test_pairing_rejects_mismatched_nonmissing_coverage():
    from equity_lab.predictive.incremental import paired_metrics

    result = paired_metrics(
        {"daily": [{"date": "2026-08-03", "rank_ic": 0.4, "count": 39}]},
        {"daily": [{"date": "2026-08-03", "rank_ic": 0.2, "count": 40}]},
    )
    assert result["valid_dates"] == 0
    assert result["daily"][0]["difference"] is None
