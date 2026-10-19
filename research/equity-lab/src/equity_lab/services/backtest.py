from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..backtest.engine import BacktestConfig, run_equal_weight_backtest
from ..backtest.prep import prepare_market_panel
from ..backtest.reporting import write_backtest_artifacts
from ..contracts.configs import validate_strategy_config
from ..data.market_data import load_market_panel
from ..paths import PROJECT_ROOT
from ..strategies import describe_strategy, discover_strategy_names, load_strategy_module
from ..utils.config import load_yaml


@dataclass(frozen=True)
class BacktestRunResult:
    strategy_name: str
    strategy_config_path: Path
    universe: list[str]
    portfolio: pd.DataFrame
    positions: pd.DataFrame
    portfolio_path: Path
    positions_path: Path
    artifact_bundle: dict[str, Any]
    comparison_runs: list[dict[str, Any]]

    @property
    def latest_equity(self) -> float:
        return float(self.portfolio.iloc[-1]["equity"])

    @property
    def total_return(self) -> float:
        return float(self.portfolio.iloc[-1]["cum_return"])

    @property
    def max_drawdown(self) -> float:
        return float(self.portfolio["drawdown"].min())


def _resolve_project_path(root: Path, value: object, default: str) -> Path:
    path = Path(str(value or default))
    return path if path.is_absolute() else root / path


def _optional_float(mapping: dict[str, Any], key: str) -> float | None:
    value = mapping.get(key)
    if value is None:
        return None
    return float(value)


def _optional_int(mapping: dict[str, Any], key: str) -> int | None:
    value = mapping.get(key)
    if value is None:
        return None
    return int(value)


def _infer_market_code(*codes: str | None) -> str:
    for raw in codes:
        if not raw:
            continue
        code = str(raw).strip().upper()
        if "." in code:
            return code.split(".", 1)[0]
    return "CN"


def _resolve_trading_dates(
    market_df: pd.DataFrame,
    backtest_cfg: dict[str, Any],
    benchmark_code: str | None = None,
    project_root: Path | None = None,
) -> tuple[pd.DatetimeIndex | None, str]:
    mode = str(backtest_cfg.get("trading_calendar_mode", "union")).strip().lower()
    fallback = "union_fallback"

    market_dates = pd.DatetimeIndex(
        pd.to_datetime(market_df["date"]).dropna().sort_values().unique()
    )
    if mode == "union":
        return market_dates, mode

    if mode == "benchmark":
        if not benchmark_code:
            return market_dates, f"{mode}_fallback_no_benchmark"
        bench_rows = market_df.loc[
            market_df["code"].astype(str) == str(benchmark_code),
            ["date"],
        ]
        if bench_rows.empty:
            return market_dates, f"{mode}_fallback_benchmark_empty"
        return (
            pd.DatetimeIndex(pd.to_datetime(bench_rows["date"]).dropna().sort_values().unique()),
            mode,
        )

    if mode == "explicit":
        path = backtest_cfg.get("trading_calendar_path")
        if not path:
            return market_dates, "explicit_fallback_no_path"
        try:
            path_obj = (
                Path(path)
                if Path(path).is_absolute()
                else _resolve_project_path(project_root or Path.cwd(), path, str(path))
            )
            explicit = pd.read_csv(path_obj, parse_dates=["date"])
            dates = pd.to_datetime(explicit["date"]).dropna().sort_values().unique()
            return pd.DatetimeIndex(dates), "explicit"
        except Exception:
            return market_dates, "explicit_fallback_read_error"

    return market_dates, fallback


def build_backtest_config(
    backtest_cfg: dict[str, Any],
    strategy_cfg: dict[str, Any],
    market_code: str | None = None,
) -> BacktestConfig:
    market_code = (
        (market_code or str(strategy_cfg.get("market", str(backtest_cfg.get("market", "CN"))))).upper()
    )
    profile = dict((backtest_cfg.get("market_cost_profiles") or {}).get(market_code, {}) or {})
    if not profile:
        profile = dict(
            (backtest_cfg.get("market_cost_profiles") or {}).get("GLOBAL", {})
            or {}
        )

    def _cost_value(key: str, fallback: float) -> float:
        value = profile.get(key)
        if value is None:
            value = backtest_cfg.get(key, fallback)
        if value is None:
            return float(fallback)
        return float(value)

    risk_limits = dict(strategy_cfg.get("risk_limits", {}) or {})
    regulation_bps = _cost_value(
        "regulation_bps",
        backtest_cfg.get("regualtion_bps", 0.0),
    )
    return BacktestConfig(
        initial_capital=float(backtest_cfg.get("initial_capital", 100000)),
        commission_bps=float(_cost_value("commission_bps", 3)),
        slippage_bps=float(_cost_value("slippage_bps", 8)),
        regulation_bps=float(regulation_bps),
        sec_fee_bps=float(_cost_value("sec_fee_bps", 0.0)),
        max_positions=_optional_int(strategy_cfg, "max_positions"),
        max_single_name_weight=_optional_float(risk_limits, "max_single_name_weight"),
        max_gross_exposure=_optional_float(risk_limits, "max_gross_exposure"),
        max_daily_turnover=_optional_float(risk_limits, "max_daily_turnover"),
    )


def _config_root(root: Path) -> Path:
    local = root / "config"
    return local if local.is_dir() else Path(__file__).resolve().parents[1] / "config"


def _default_backtest_config_path(root: Path) -> Path:
    return Path(os.getenv("EQUITY_LAB_BACKTEST_CONFIG", str(_config_root(root) / "backtest" / "default.yaml")))


def _default_strategy_config_path(root: Path, default_config_name: str) -> Path:
    return Path(
        os.getenv(
            "EQUITY_LAB_STRATEGY_CONFIG",
            str(_config_root(root) / "strategies" / f"{default_config_name}.yaml"),
        )
    )


def _default_universe_path(root: Path, universe_name: object) -> Path:
    return Path(
        os.getenv(
            "EQUITY_LAB_UNIVERSE_FILE",
            str(_config_root(root) / "universe" / f"{universe_name}.txt"),
        )
    )


def _path_for_summary(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _resolve_strategy_config_path(
    root: Path,
    strategy_spec,
) -> Path:
    candidate = _config_root(root) / "strategies" / f"{strategy_spec.default_config_name}.yaml"
    if not candidate.exists():
        candidate = _config_root(root) / "strategies" / f"{strategy_spec.name}.yaml"
    if not candidate.exists():
        raise FileNotFoundError(f"Missing strategy config for {strategy_spec.name}: {candidate}")
    return candidate


def _collect_market_metadata(
    market_df: pd.DataFrame,
    market_root: Path,
    root: Path,
    backtest_cfg: dict[str, Any],
    backtest_config_path: Path,
    trading_dates: pd.DatetimeIndex | None = None,
    trading_calendar_source: str | None = None,
) -> tuple[dict[str, Any], pd.Series | None, str | None]:
    bench_code = backtest_cfg.get("benchmark")
    bench_series = None
    if bench_code:
        benchmark_rows = market_df.loc[
            market_df["code"].astype(str) == str(bench_code),
            ["date", "close"],
        ].copy()
        if not benchmark_rows.empty:
            benchmark_rows["date"] = pd.to_datetime(benchmark_rows["date"])
            benchmark_rows = benchmark_rows.sort_values("date")
            benchmark_rows["close"] = pd.to_numeric(benchmark_rows["close"], errors="coerce")
            bench_series = (
                benchmark_rows.dropna(subset=["close"])
                .set_index("date")["close"]
                .pct_change()
                .fillna(0.0)
            )

    if market_df.empty:
        return {}, None, None

    market_files = list(market_root.glob("*.csv"))
    latest_mtime = None
    if market_files:
        latest = max(path.stat().st_mtime for path in market_files)
        latest_mtime = pd.to_datetime(latest, unit="s", utc=True).isoformat()

    run_metadata = {
        "market_data_path": _path_for_summary(market_root, root),
        "market_data_files": int(len(market_files)),
        "market_data_latest_mtime_utc": latest_mtime,
        "market_rows": int(len(market_df)),
        "market_date_min": pd.to_datetime(market_df["date"]).min().date().isoformat(),
        "market_date_max": pd.to_datetime(market_df["date"]).max().date().isoformat(),
        "trading_calendar_mode": str(backtest_cfg.get("trading_calendar_mode", "union")),
        "trading_calendar_source": trading_calendar_source,
        "trading_calendar_days": None,
        "trading_calendar_coverage_ratio": None,
        "backtest_config_path": _path_for_summary(backtest_config_path, root),
        "executed_at_utc": datetime.now(UTC).isoformat(),
        "backtest_name": str(backtest_cfg.get("name", "")),
        "benchmark": str(bench_code) if bench_code is not None else None,
    }
    if trading_dates is not None:
        market_dates = pd.DatetimeIndex(pd.to_datetime(market_df["date"]).dropna().sort_values().unique())
        run_metadata["trading_calendar_days"] = int(len(trading_dates))
        if len(trading_dates):
            run_metadata["trading_calendar_coverage_ratio"] = float(
                market_dates.isin(trading_dates).sum() / len(trading_dates)
            )
    return run_metadata, bench_series, str(bench_code) if bench_code is not None else None


def _coerce_benchmark_names(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        names = [str(x).strip() for x in raw]
        return [x for x in names if x]
    names = []
    for item in str(raw).split(","):
        value = item.strip()
        if value:
            names.append(value)
    return names


def _merge_strategy_configs(
    target_cfg: dict[str, Any],
    baseline_cfg: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(baseline_cfg)
    merged.setdefault("universe", target_cfg.get("universe", "hk_core_watchlist"))
    merged.setdefault("position_sizing", "equal_weight")
    merged.setdefault("max_positions", target_cfg.get("max_positions"))
    merged.setdefault(
        "risk_limits",
        dict(target_cfg.get("risk_limits", {}) or {}),
    )
    merged.setdefault("signal", {})
    merged.setdefault("name", baseline_cfg.get("name"))
    merged.setdefault("signal", dict(merged.get("signal", {}) or {}))
    if "signal" not in merged or not isinstance(merged["signal"], dict):
        merged["signal"] = {}
    return merged


def _safe_signal_build(
    strategy_module,
    market_df: pd.DataFrame,
    signal_kwargs: dict[str, Any],
    strategy_name: str,
) -> pd.DataFrame:
    try:
        return strategy_module.build_signal_frame(market_df, **signal_kwargs)
    except Exception as exc:
        fallback = market_df.copy().sort_values(["code", "date"]).reset_index(drop=True)
        fallback["signal"] = 0
        fallback["weight_score"] = 0.0
        fallback["target_weight"] = 0.0
        fallback["future_return"] = (
            fallback.groupby("code")["close"].shift(-1) / fallback["close"] - 1.0
        )
        fallback["target_label"] = 0.0
        fallback["signal_strategy"] = strategy_name
        fallback["strategy_fallback"] = True
        fallback["strategy_fallback_reason"] = f"{type(exc).__name__}: {exc}"
        return fallback


def _run_single_strategy(
    *,
    strategy_name: str,
    market_df: pd.DataFrame,
    strategy_cfg: dict[str, Any],
    backtest_cfg: dict[str, Any],
    strategy_module,
    strategy_spec,
    project_root: Path,
    report_root: Path,
    strategy_config_path: Path,
    market_code: str,
    benchmark_code: str | None,
    benchmark_returns: pd.Series | None,
    run_metadata: dict[str, Any],
    report_subdir: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], pd.DataFrame]:
    signal_kwargs: dict[str, Any] = dict(strategy_spec.default_signal_kwargs)
    signal_kwargs.update(dict(strategy_cfg.get("signal", {}) or {}))
    max_positions = strategy_cfg.get("max_positions")
    if strategy_name == "random_turnover" and max_positions is not None:
        signal_kwargs["selection_top_n"] = int(max_positions)

    signal_df = _safe_signal_build(strategy_module, market_df, signal_kwargs, strategy_name)

    portfolio, positions = run_equal_weight_backtest(
        signal_df,
        build_backtest_config(backtest_cfg, strategy_cfg, market_code),
    )

    report_dir = report_root / report_subdir
    report_dir.mkdir(parents=True, exist_ok=True)
    portfolio.to_csv(report_dir / "portfolio_daily.csv", index=False)
    positions.to_csv(report_dir / "positions_daily.csv", index=False)

    artifact_bundle = write_backtest_artifacts(
        report_dir,
        portfolio,
        positions,
        signal_df=signal_df,
        benchmark_code=benchmark_code,
        benchmark_returns=benchmark_returns,
        run_metadata=dict(run_metadata),
        strategy_name=strategy_spec.name,
        strategy_config=_path_for_summary(strategy_config_path, project_root),
        universe=list(signal_df["code"].drop_duplicates()),
        initial_capital=float(backtest_cfg.get("initial_capital", 100000)),
    )

    summary = artifact_bundle["summary"]["metrics"]
    return (
        portfolio,
        positions,
        {
            "strategy": strategy_name,
            "status": artifact_bundle["summary"]["run_status"],
            "fallback_reasons": artifact_bundle["summary"]["fallback_reasons"],
            "strategy_config": strategy_config_path.name,
            "total_return": summary.get("total_return"),
            "annualized_return": summary.get("annualized_return"),
            "sharpe_ratio": summary.get("sharpe_ratio"),
            "max_drawdown": summary.get("max_drawdown"),
            "summary_path": str(artifact_bundle["summary_path"]),
            "oos_signal_hit_rate": summary.get("oos_signal_hit_rate"),
            "oos_ic": summary.get("oos_ic"),
            "oos_rank_ic": summary.get("oos_rank_ic"),
            "is_signal_hit_rate": summary.get("is_signal_hit_rate"),
            "is_ic": summary.get("is_ic"),
            "is_rank_ic": summary.get("is_rank_ic"),
            "walk_forward_summary": artifact_bundle["summary"].get("walk_forward", {}),
        },
        signal_df,
    )


def run_backtest_service(
    strategy_name: str = "sma_cross",
    *,
    root: Path | None = None,
    config_path: Path | None = None,
    strategy_config_path: Path | None = None,
    universe_path: Path | None = None,
    compare_benchmarks: bool = False,
    benchmark_list: str | None = None,
) -> BacktestRunResult:
    project_root = root or PROJECT_ROOT
    strategy_module = load_strategy_module(strategy_name)
    strategy_spec = describe_strategy(strategy_name)

    resolved_config_path = config_path or _default_backtest_config_path(project_root)
    resolved_strategy_path = strategy_config_path or _default_strategy_config_path(
        project_root,
        strategy_spec.default_config_name,
    )
    strategy_cfg = load_yaml(resolved_strategy_path)
    backtest_cfg = load_yaml(resolved_config_path)
    validate_strategy_config(strategy_cfg, strategy_spec.required_config_keys)

    universe_name = strategy_cfg.get("universe", "hk_core_watchlist")
    resolved_universe_path = universe_path or _default_universe_path(project_root, universe_name)
    codes = strategy_module.load_universe(resolved_universe_path)

    market_root = _resolve_project_path(
        project_root,
        backtest_cfg.get("price_path"),
        "artifacts/data/processed/market",
    )
    raw_market_df = load_market_panel(market_root, codes)
    benchmark_code = backtest_cfg.get("benchmark")
    trading_dates, trading_calendar_source = _resolve_trading_dates(
        raw_market_df,
        backtest_cfg=backtest_cfg,
        benchmark_code=str(benchmark_code) if benchmark_code is not None else None,
        project_root=project_root,
    )
    market_df = prepare_market_panel(raw_market_df, trading_dates=trading_dates)
    market_code = str(
        strategy_cfg.get("market") or backtest_cfg.get("market")
        or _infer_market_code(benchmark_code, *codes)
    ).strip().upper()

    run_metadata, benchmark_returns, benchmark_code = _collect_market_metadata(
        market_df,
        market_root,
        project_root,
        backtest_cfg,
        resolved_config_path,
        trading_dates=trading_dates,
        trading_calendar_source=trading_calendar_source,
    )
    if strategy_name == "cnn_walk_forward_rank" and len(market_df) > 0:
        run_metadata["walk_forward_min_days_required"] = 1260 + 252 + 252
        run_metadata["walk_forward_market_days_available"] = int(
            len(market_df["date"].drop_duplicates())
        )
        run_metadata["walk_forward_history_ok"] = bool(
            run_metadata["walk_forward_market_days_available"] >= run_metadata["walk_forward_min_days_required"]
        )

    run_metadata["signal_config_path"] = _path_for_summary(resolved_strategy_path, project_root)
    run_metadata["strategy_name"] = strategy_spec.name
    run_metadata["strategy_requested"] = strategy_name
    run_metadata["universe_size_requested"] = len(codes)

    report_root = _resolve_project_path(
        project_root,
        backtest_cfg.get("report_path"),
        "artifacts/reports/backtests",
    )
    report_root.mkdir(parents=True, exist_ok=True)

    target_portfolio, target_positions, target_summary, target_signal = _run_single_strategy(
        strategy_name=strategy_name,
        market_df=market_df,
        strategy_cfg=strategy_cfg,
        backtest_cfg=backtest_cfg,
        strategy_module=strategy_module,
        strategy_spec=strategy_spec,
        project_root=project_root,
        report_root=report_root,
        strategy_config_path=resolved_strategy_path,
        market_code=market_code,
        benchmark_code=benchmark_code,
        benchmark_returns=benchmark_returns,
        run_metadata=run_metadata,
        report_subdir=".",
    )

    comparison_runs: list[dict[str, Any]] = []
    if compare_benchmarks:
        names = _coerce_benchmark_names(
            benchmark_list or backtest_cfg.get("benchmark_strategies")
        )
        available = set(discover_strategy_names())
        for name in names:
            if name == strategy_name or name not in available:
                continue
            try:
                base_module = load_strategy_module(name)
                base_spec = describe_strategy(name)
                base_config_path = _resolve_strategy_config_path(project_root, base_spec)
                base_cfg = _merge_strategy_configs(strategy_cfg, load_yaml(base_config_path))
                validate_strategy_config(base_cfg, base_spec.required_config_keys)
                _, _, summary, _ = _run_single_strategy(
                    strategy_name=name,
                    market_df=market_df,
                    strategy_cfg=base_cfg,
                    backtest_cfg=backtest_cfg,
                    strategy_module=base_module,
                    strategy_spec=base_spec,
                    project_root=project_root,
                    report_root=report_root,
                    strategy_config_path=base_config_path,
                    market_code=market_code,
                    benchmark_code=benchmark_code,
                    benchmark_returns=None,
                    run_metadata={"benchmark_of": strategy_name},
                    report_subdir=f"benchmark_{name}",
                )
                comparison_runs.append(summary)
            except Exception as exc:
                comparison_runs.append(
                    {
                        "strategy": name,
                        "status": "failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    target_artifact = write_backtest_artifacts(
        report_root,
        target_portfolio,
        target_positions,
        signal_df=target_signal,
        benchmark_code=benchmark_code,
        benchmark_returns=benchmark_returns,
        run_metadata=run_metadata,
        strategy_name=strategy_spec.name,
        strategy_config=_path_for_summary(resolved_strategy_path, project_root),
        universe=codes,
        initial_capital=float(backtest_cfg.get("initial_capital", 100000)),
        comparison_runs=comparison_runs,
    )

    portfolio_path = report_root / "portfolio_daily.csv"
    positions_path = report_root / "positions_daily.csv"

    return BacktestRunResult(
        strategy_name=strategy_spec.name,
        strategy_config_path=resolved_strategy_path,
        universe=codes,
        portfolio=target_portfolio,
        positions=target_positions,
        portfolio_path=portfolio_path,
        positions_path=positions_path,
        artifact_bundle=target_artifact,
        comparison_runs=comparison_runs,
    )
