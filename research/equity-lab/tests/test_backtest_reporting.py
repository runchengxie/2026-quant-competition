from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from equity_lab.backtest.reporting import write_backtest_artifacts


def test_write_backtest_artifacts_creates_summary_and_monthly_outputs(tmp_path: Path) -> None:
    portfolio_df = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "daily_return": 0.0,
                "equity": 100000.0,
                "turnover": 0.0,
                "gross_exposure": 0.0,
            },
            {
                "date": "2024-01-02",
                "daily_return": 0.10,
                "equity": 110000.0,
                "turnover": 1.0,
                "gross_exposure": 1.0,
            },
            {
                "date": "2024-02-01",
                "daily_return": 0.02,
                "equity": 112200.0,
                "turnover": 0.1,
                "gross_exposure": 1.0,
            },
        ]
    )
    positions_df = pd.DataFrame(
        [
            {"date": "2024-01-02", "code": "AAA", "target_weight": 1.0},
            {"date": "2024-02-01", "code": "AAA", "target_weight": 1.0},
        ]
    )

    bundle = write_backtest_artifacts(
        tmp_path,
        portfolio_df,
        positions_df,
        strategy_name="SMA Cross",
        strategy_config="config/strategies/sim_portfolio.yaml",
        universe=["AAA"],
        initial_capital=100000.0,
    )

    summary_path = bundle["summary_path"]
    monthly_path = bundle["monthly_returns_path"]
    drawdown_path = bundle["drawdown_path"]

    assert summary_path.exists()
    assert monthly_path.exists()
    assert drawdown_path.exists()

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["strategy"] == "SMA Cross"
    assert payload["metrics"]["final_equity"] == 112200.0
    assert payload["artifacts"]["monthly_returns"] == "monthly_returns.csv"


def test_write_backtest_artifacts_summarizes_walk_forward_metrics(tmp_path: Path) -> None:
    portfolio_df = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "daily_return": 0.0,
                "equity": 100000.0,
                "turnover": 0.0,
                "gross_exposure": 0.0,
            },
            {
                "date": "2024-01-02",
                "daily_return": 0.01,
                "equity": 101000.0,
                "turnover": 0.5,
                "gross_exposure": 1.0,
            },
        ]
    )
    positions_df = pd.DataFrame(
        [{"date": "2024-01-02", "code": "AAA", "target_weight": 1.0}]
    )
    signal_df = pd.DataFrame(
        [{"date": "2024-01-02", "code": "AAA", "signal": 1, "target_label": 1}]
    )
    signal_df.attrs["cnn_walk_forward_fold_stats"] = [
        {
            "status": "trained",
            "train_count": 100,
            "validation_count": 20,
            "test_count": 30,
            "test_selected_signal_count": 5,
            "test_selected_hit_rate": 0.6,
            "test_selected_mean_future_return": 0.02,
            "test_auc": 0.55,
            "test_ic": 0.10,
            "test_rank_ic": 0.12,
            "purge_days": 5,
            "embargo_days": 5,
        },
        {
            "status": "trained",
            "train_count": 100,
            "validation_count": 20,
            "test_count": 30,
            "test_selected_signal_count": 4,
            "test_selected_hit_rate": 0.5,
            "test_selected_mean_future_return": 0.01,
            "test_auc": 0.51,
            "test_ic": 0.02,
            "test_rank_ic": 0.04,
            "purge_days": 5,
            "embargo_days": 5,
        },
    ]

    bundle = write_backtest_artifacts(
        tmp_path,
        portfolio_df,
        positions_df,
        signal_df=signal_df,
        strategy_name="Walk Forward",
        strategy_config="config/strategies/cnn_walk_forward_rank.yaml",
        universe=["AAA"],
        initial_capital=100000.0,
    )

    walk_forward = bundle["summary"]["walk_forward"]
    assert walk_forward["trained_folds"] == 2
    assert walk_forward["oos_selected_signal_count"] == 9
    assert walk_forward["avg_oos_auc"] == pytest.approx(0.53)
    assert walk_forward["avg_oos_rank_ic"] == pytest.approx(0.08)
    assert walk_forward["purge_days"] == 5
    assert walk_forward["embargo_days"] == 5


def test_write_backtest_artifacts_writes_prediction_decile_returns(tmp_path: Path) -> None:
    portfolio_df = pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "daily_return": 0.0,
                "equity": 100000.0,
                "turnover": 0.0,
                "gross_exposure": 0.0,
            }
        ]
    )
    positions_df = pd.DataFrame(
        [{"date": "2024-01-01", "code": "AAA", "target_weight": 1.0}]
    )
    signal_rows = []
    for idx in range(12):
        signal_rows.append(
            {
                "date": "2024-01-01",
                "code": f"AAA{idx:02d}",
                "cnn_probability": idx / 11,
                "future_return": (idx - 5) / 100,
                "signal": int(idx >= 8),
                "target_label": int(idx >= 6),
            }
        )
    signal_df = pd.DataFrame(signal_rows)

    bundle = write_backtest_artifacts(
        tmp_path,
        portfolio_df,
        positions_df,
        signal_df=signal_df,
        strategy_name="CNN Image",
        strategy_config="config/strategies/cnn_image_pattern.yaml",
        universe=["AAA"],
        initial_capital=100000.0,
    )

    payload = json.loads(bundle["summary_path"].read_text(encoding="utf-8"))
    assert payload["artifacts"]["prediction_decile_returns"] == "prediction_decile_returns.csv"
    deciles = pd.read_csv(tmp_path / "prediction_decile_returns.csv")
    assert "ALL" in set(deciles["date"])
    assert deciles["decile"].max() == 10
    assert deciles.loc[deciles["date"].eq("ALL"), "mean_future_return"].notna().all()
