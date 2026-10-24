from __future__ import annotations

import json
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..evaluation.performance import compute_backtest_metrics, compute_drawdown_series


@dataclass(frozen=True)
class BacktestArtifactOptions:
    strategy_name: str
    strategy_config: str
    universe: list[str]
    initial_capital: float
    annual_risk_free_rate: float = 0.0


def _resolve_artifact_options(
    options: BacktestArtifactOptions | None,
    overrides: dict[str, Any],
) -> BacktestArtifactOptions:
    if options is None:
        required = {"strategy_name", "strategy_config", "universe", "initial_capital"}
        missing = required - set(overrides)
        if missing:
            raise TypeError(f"missing artifact options: {sorted(missing)}")
        options = BacktestArtifactOptions(
            strategy_name=str(overrides.pop("strategy_name")),
            strategy_config=str(overrides.pop("strategy_config")),
            universe=list(overrides.pop("universe")),
            initial_capital=float(overrides.pop("initial_capital")),
        )

    allowed = {field.name for field in fields(BacktestArtifactOptions)}
    unknown = set(overrides) - allowed
    if unknown:
        raise TypeError(f"unknown artifact options: {sorted(unknown)}")
    return replace(options, **overrides) if overrides else options


def _mean_numeric(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.mean())


def _sum_numeric(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns:
        return 0
    return int(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def _t_stat_numeric(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    if len(values) < 2:
        return None
    std = float(values.std(ddof=1))
    if std == 0.0 or pd.isna(std):
        return None
    return float(values.mean() / (std / np.sqrt(len(values))))


def _groupby_date_label(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _groupby_int_key(value: Any) -> int:
    return int(value)


def _build_monthly_returns(portfolio_df: pd.DataFrame) -> pd.DataFrame:
    df = portfolio_df.loc[:, ["date", "daily_return"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M").astype(str)
    rows: list[dict[str, float | str]] = []
    for month, group in df.groupby("month", sort=True):
        returns = pd.to_numeric(group["daily_return"], errors="coerce").fillna(0.0).astype(float)
        growth = np.prod(1.0 + returns.to_numpy(dtype=float))
        rows.append(
            {
                "month": str(month),
                "monthly_return": float(growth - 1.0),
            }
        )
    return pd.DataFrame(rows, columns=["month", "monthly_return"])


def _maybe_write_equity_plot(portfolio_df: pd.DataFrame, output_path: Path) -> Path | None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return None

    df = portfolio_df.loc[:, ["date", "equity"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.plot(df["date"], df["equity"], linewidth=1.8, color="#1f77b4")
    ax.set_title("Backtest Equity Curve")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def _walk_forward_summary(signal_df: pd.DataFrame) -> dict[str, Any]:
    fold_stats = signal_df.attrs.get("cnn_walk_forward_fold_stats")
    if not isinstance(fold_stats, list) or not fold_stats:
        return {}

    df = pd.DataFrame(fold_stats)
    result: dict[str, Any] = {
        "total_folds": int(len(df)),
        "trained_folds": int((df["status"] == "trained").sum()),
        "test_rows": int(pd.to_numeric(df["test_count"], errors="coerce").fillna(0).sum()),
        "validation_rows": int(pd.to_numeric(df["validation_count"], errors="coerce").fillna(0).sum()),
        "train_rows": int(pd.to_numeric(df["train_count"], errors="coerce").fillna(0).sum()),
    }
    trained = df[df["status"] == "trained"]
    if not trained.empty:
        result["oos_selected_signal_count"] = _sum_numeric(
            trained,
            "test_selected_signal_count",
        )
        result["avg_oos_hit_rate"] = _mean_numeric(trained, "test_selected_hit_rate")
        result["avg_oos_mean_return"] = _mean_numeric(
            trained,
            "test_selected_mean_future_return",
        )
        result["avg_oos_auc"] = _mean_numeric(trained, "test_auc")
        result["avg_oos_ic"] = _mean_numeric(trained, "test_ic")
        result["avg_oos_rank_ic"] = _mean_numeric(trained, "test_rank_ic")
        result["oos_mean_return_t_stat"] = _t_stat_numeric(
            trained,
            "test_selected_mean_future_return",
        )
        result["purge_days"] = (
            int(pd.to_numeric(trained["purge_days"], errors="coerce").max())
            if "purge_days" in trained.columns
            else None
        )
        result["embargo_days"] = (
            int(pd.to_numeric(trained["embargo_days"], errors="coerce").max())
            if "embargo_days" in trained.columns
            else None
        )
    return result


def _build_prediction_decile_returns(signal_df: pd.DataFrame) -> pd.DataFrame:
    if signal_df.empty or "date" not in signal_df.columns or "future_return" not in signal_df.columns:
        return pd.DataFrame()

    score_column = None
    for candidate in ("weight_score", "cnn_calibrated_probability", "cnn_probability", "signal"):
        if candidate in signal_df.columns:
            score_column = candidate
            break
    if score_column is None:
        return pd.DataFrame()

    frame = signal_df.loc[:, ["date", "code", score_column, "future_return"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.floor("D")
    frame["score"] = pd.to_numeric(frame[score_column], errors="coerce")
    frame["future_return"] = pd.to_numeric(frame["future_return"], errors="coerce")
    frame = frame.dropna(subset=["date", "score", "future_return"])
    if frame.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for date, group in frame.groupby("date", sort=True):
        ranked = group.copy()
        if ranked["score"].nunique() < 2:
            continue
        ranked["decile"] = pd.qcut(
            ranked["score"].rank(method="first"),
            q=min(10, len(ranked)),
            labels=False,
            duplicates="drop",
        )
        ranked = ranked.dropna(subset=["decile"])
        if ranked.empty:
            continue
        ranked["decile"] = ranked["decile"].astype(int) + 1
        for decile, decile_group in ranked.groupby("decile", sort=True):
            returns = pd.to_numeric(decile_group["future_return"], errors="coerce").dropna()
            if returns.empty:
                continue
            rows.append(
                {
                    "date": _groupby_date_label(date),
                    "score_column": score_column,
                    "decile": _groupby_int_key(decile),
                    "count": int(len(returns)),
                    "mean_future_return": float(returns.mean()),
                    "median_future_return": float(returns.median()),
                    "hit_rate": float((returns > 0.0).mean()),
                    "score_min": float(decile_group["score"].min()),
                    "score_max": float(decile_group["score"].max()),
                }
            )

    if not rows:
        return pd.DataFrame()
    daily = pd.DataFrame.from_records(rows)
    summary_rows: list[dict[str, Any]] = []
    for decile, group in daily.groupby("decile", sort=True):
        summary_rows.append(
            {
                "date": "ALL",
                "score_column": score_column,
                "decile": _groupby_int_key(decile),
                "count": int(pd.to_numeric(group["count"], errors="coerce").sum()),
                "mean_future_return": float(pd.to_numeric(group["mean_future_return"], errors="coerce").mean()),
                "median_future_return": float(pd.to_numeric(group["median_future_return"], errors="coerce").mean()),
                "hit_rate": float(pd.to_numeric(group["hit_rate"], errors="coerce").mean()),
                "score_min": float(pd.to_numeric(group["score_min"], errors="coerce").min()),
                "score_max": float(pd.to_numeric(group["score_max"], errors="coerce").max()),
            }
        )
    return pd.concat([pd.DataFrame.from_records(summary_rows), daily], ignore_index=True)


def _write_comparison_outputs(report_dir: Path, comparison_runs: list[dict[str, Any]]) -> dict[str, str]:
    comparison_dir = report_dir / "comparison"
    comparison_dir.mkdir(parents=True, exist_ok=True)
    comparison_path = comparison_dir / "comparison_summary.csv"
    comparison_df = pd.DataFrame(comparison_runs)
    comparison_df.to_csv(comparison_path, index=False)
    comparison_json = comparison_dir / "comparison_summary.json"
    comparison_json.write_text(
        json.dumps(
            {
                "benchmark_runs": comparison_df.to_dict(orient="records"),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "comparison_csv": comparison_path.name,
        "comparison_json": comparison_json.name,
    }


def write_backtest_artifacts(
    report_dir: Path,
    portfolio_df: pd.DataFrame,
    positions_df: pd.DataFrame,
    *,
    options: BacktestArtifactOptions | None = None,
    signal_df: pd.DataFrame | None = None,
    run_metadata: dict[str, Any] | None = None,
    benchmark_code: str | None = None,
    benchmark_returns: pd.Series | None = None,
    comparison_runs: list[dict[str, Any]] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    artifact_options = _resolve_artifact_options(options, overrides)
    report_dir.mkdir(parents=True, exist_ok=True)

    walk_forward_summary = {}
    walk_forward_folds_path = None
    prediction_deciles_path = None
    if signal_df is not None:
        walk_forward_summary = _walk_forward_summary(signal_df)
        walk_forward_folds = signal_df.attrs.get("cnn_walk_forward_fold_stats")
        if isinstance(walk_forward_folds, list) and walk_forward_folds:
            walk_forward_folds_df = pd.DataFrame(walk_forward_folds)
            walk_forward_folds_path = report_dir / "cnn_walk_forward_fold_stats.csv"
            walk_forward_folds_df.to_csv(walk_forward_folds_path, index=False)
        prediction_deciles = _build_prediction_decile_returns(signal_df)
        if not prediction_deciles.empty:
            prediction_deciles_path = report_dir / "prediction_decile_returns.csv"
            prediction_deciles.to_csv(prediction_deciles_path, index=False)

    metrics = compute_backtest_metrics(
        portfolio_df,
        initial_capital=artifact_options.initial_capital,
        annual_risk_free_rate=artifact_options.annual_risk_free_rate,
        signal_df=signal_df,
        benchmark_returns=benchmark_returns,
    )
    metrics["walk_forward"] = walk_forward_summary

    monthly_returns = _build_monthly_returns(portfolio_df)
    monthly_returns_path = report_dir / "monthly_returns.csv"
    monthly_returns.to_csv(monthly_returns_path, index=False)

    drawdown_df = portfolio_df.loc[:, ["date", "equity"]].copy()
    drawdown_df["drawdown"] = compute_drawdown_series(drawdown_df["equity"]).to_numpy()
    drawdown_path = report_dir / "drawdown_daily.csv"
    drawdown_df.to_csv(drawdown_path, index=False)

    plot_path = _maybe_write_equity_plot(portfolio_df, report_dir / "equity_curve.png")
    comparison_payload: dict[str, Any] | None = None
    if comparison_runs:
        comparison_payload = dict(_write_comparison_outputs(report_dir, comparison_runs))
        comparison_payload["benchmark_count"] = int(len(comparison_runs))

    fallback_reasons = []
    if signal_df is not None and "strategy_fallback_reason" in signal_df:
        fallback_reasons = signal_df["strategy_fallback_reason"].dropna().astype(str).unique().tolist()
    summary = {
        "run_status": "strategy_fallback" if fallback_reasons else "completed",
        "fallback_reasons": fallback_reasons,
        "strategy": artifact_options.strategy_name,
        "strategy_config": artifact_options.strategy_config,
        "universe": list(artifact_options.universe),
        "portfolio_rows": int(len(portfolio_df)),
        "positions_rows": int(len(positions_df)),
        "metrics": metrics,
        "artifacts": {
            "portfolio_daily": "portfolio_daily.csv",
            "positions_daily": "positions_daily.csv",
            "monthly_returns": monthly_returns_path.name,
            "drawdown_daily": drawdown_path.name,
            "equity_curve_png": plot_path.name if plot_path is not None else None,
            "cnn_walk_forward_fold_stats": (
                walk_forward_folds_path.name if walk_forward_folds_path is not None else None
            ),
            "prediction_decile_returns": (
                prediction_deciles_path.name if prediction_deciles_path is not None else None
            ),
        },
        "benchmark_code": benchmark_code,
        "walk_forward": walk_forward_summary,
        "comparison": comparison_payload,
        "run_metadata": run_metadata or {},
    }

    summary_path = report_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "summary": summary,
        "summary_path": summary_path,
        "monthly_returns_path": monthly_returns_path,
        "drawdown_path": drawdown_path,
        "equity_curve_path": plot_path,
    }
