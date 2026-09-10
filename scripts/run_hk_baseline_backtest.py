from __future__ import annotations

import argparse
import json
from pathlib import Path

from strategies.hk_low_frequency import HKBacktestConfig, load_daily_csv, run_monthly_backtest
from strategies.international_lite.evaluation import evaluate_competition_metrics


def _metrics(metrics) -> dict[str, float]:
    return {
        "cumulative_return": metrics.cumulative_return,
        "sharpe": metrics.sharpe,
        "max_drawdown": metrics.max_drawdown,
        "positive_period_fraction": metrics.positive_period_fraction,
    }


def _buy_and_hold(bars):
    returns = [bars[index].close / bars[index - 1].close - 1.0 for index in range(1, len(bars))]
    return evaluate_competition_metrics(returns), returns


def build_report(data_root: Path, benchmark_path: Path, cost_bps: float) -> dict:
    paths = sorted(data_root.glob("*.csv"))
    if not paths:
        raise ValueError(f"no stock CSV files found under {data_root}")
    history = {path.stem: load_daily_csv(path) for path in paths}
    benchmark = load_daily_csv(benchmark_path)
    config = HKBacktestConfig(commission_bps=cost_bps / 2, slippage_bps=cost_bps / 2)
    pure_config = HKBacktestConfig(
        commission_bps=cost_bps / 2,
        slippage_bps=cost_bps / 2,
        mode="pure_momentum",
    )
    combo = run_monthly_backtest(history, benchmark, config)
    pure = run_monthly_backtest(history, benchmark, pure_config)
    benchmark_metrics, benchmark_returns = _buy_and_hold(benchmark)
    def strategy_payload(result):
        return {
            "metrics": _metrics(result.metrics),
            "benchmark_metrics_on_same_dates": _metrics(result.benchmark_metrics),
            "average_rebalance_turnover": result.average_turnover,
            "holding_rate": result.holding_rate,
            "empty_days": result.empty_days,
            "rebalance_count": len(result.rebalances),
            "sample_start": result.dates[0],
            "sample_end": result.dates[-1],
        }
    return {
        "as_of": "2026-09-10",
        "data": {
            "stock_root": str(data_root),
            "benchmark_path": str(benchmark_path),
            "stock_count": len(history),
            "stock_rows": {symbol: len(bars) for symbol, bars in history.items()},
            "stock_start": min(bars[0].date for bars in history.values()),
            "stock_end": max(bars[-1].date for bars in history.values()),
            "benchmark_rows": len(benchmark),
            "benchmark_start": benchmark[0].date,
            "benchmark_end": benchmark[-1].date,
        },
        "assumptions": {
            "rebalance": "first shared trading date of each month, signal as of prior shared date",
            "execution": "next-session close-to-close proxy because only daily close is available",
            "commission_plus_slippage_bps": cost_bps,
            "top_k": config.top_k,
            "max_weight": config.max_weight,
            "cash_weight": config.cash_weight,
            "lookbacks": config.lookbacks,
            "momentum_weights": config.momentum_weights,
            "volatility_window": config.volatility_window,
        },
        "strategies": {
            "2800_buy_and_hold": {"metrics": _metrics(benchmark_metrics), "sample_start": benchmark[1].date, "sample_end": benchmark[-1].date},
            "pure_momentum": strategy_payload(pure),
            "momentum_volatility": strategy_payload(combo),
        },
        "limitations": [
            "Only 20 HK stocks are available; this is not a complete historical competition universe.",
            "No point-in-time constituents or fundamentals are used.",
            "No realtime, bid/ask, depth, tick, or order-level data is used.",
            "Daily close execution is a research proxy and does not prove live fillability.",
            "Competition rule interpretation, benchmark, and turnover threshold still require organizer confirmation.",
        ],
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# 港股低频动量 + 波动率基线回测",
        "",
        f"- 快照日期：{report['as_of']}",
        f"- 股票数量：{report['data']['stock_count']}",
        f"- 股票样本：{report['data']['stock_start']} 至 {report['data']['stock_end']}",
        f"- 基准：`HK_2800.csv`，{report['data']['benchmark_start']} 至 {report['data']['benchmark_end']}",
        f"- 成本假设：佣金 + 滑点合计 {report['assumptions']['commission_plus_slippage_bps']} bps",
        "",
        "## 比较结果",
        "",
        "| 组合 | 累计收益 | Sharpe | 最大回撤 | 正收益日占比 | 调仓次数 | 平均调仓换手 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, item in report["strategies"].items():
        metrics = item["metrics"]
        lines.append(
            f"| {name} | {metrics['cumulative_return']:.2%} | {metrics['sharpe']:.2f} | {metrics['max_drawdown']:.2%} | "
            f"{metrics['positive_period_fraction']:.2%} | {item.get('rebalance_count', 0)} | {item.get('average_rebalance_turnover', 0):.2%} |"
        )
    lines.extend(["", "## 解释与限制", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.extend([
        "",
        "该结果仅证明在当前 20 只港股日线快照上的历史研究表现；不能证明已经具备韩国/港股实时行情权限，也不能直接作为实盘下单许可。",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path(r"D:\data\hk-competition-2026\raw\ibkr\daily"))
    parser.add_argument("--benchmark", type=Path, default=Path(r"D:\data\global-six-market\raw\ibkr\daily\HK_2800.csv"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/hk-baseline-2026-09-10.json"))
    parser.add_argument("--cost-bps", type=float, default=10.0)
    args = parser.parse_args()
    report = build_report(args.data_root, args.benchmark, args.cost_bps)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["strategies"], ensure_ascii=False, indent=2))
    print(f"WROTE {args.output}")
    print(f"WROTE {markdown_path}")


if __name__ == "__main__":
    main()
