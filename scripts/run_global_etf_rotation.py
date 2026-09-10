from __future__ import annotations

import argparse
import json
from pathlib import Path

from strategies.global_etf_rotation import GlobalETFConfig, load_daily_csv, run_monthly_rotation
from strategies.international_lite.evaluation import evaluate_competition_metrics


ASSETS = ("US_SPY", "HK_2800", "UK_ISF", "AU_STW", "CA_XIU", "SG_ES3")


def metrics(item):
    return {"cumulative_return": item.cumulative_return, "sharpe": item.sharpe, "max_drawdown": item.max_drawdown, "positive_period_fraction": item.positive_period_fraction}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path(r"D:\data\global-six-market\raw\ibkr\daily"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/global-etf-rotation-2026-09-10.json"))
    args = parser.parse_args()
    history = {symbol: load_daily_csv(args.data_root / f"{symbol}.csv") for symbol in ASSETS}
    config = GlobalETFConfig()
    pure = run_monthly_rotation(history, GlobalETFConfig(mode="pure_momentum"))
    defended = run_monthly_rotation(history, config)
    equal_weight = evaluate_competition_metrics(defended.benchmark_returns)
    report = {
        "as_of": "2026-09-10",
        "assets": ASSETS,
        "data": {symbol: {"rows": len(bars), "start": bars[0].date, "end": bars[-1].date} for symbol, bars in history.items()},
        "common_sample": {"start": defended.dates[0], "end": defended.dates[-1], "rows": len(defended.dates)},
        "assumptions": {"rebalance": "monthly", "signal": "prior common trading date", "top_k": config.top_k, "max_weight": config.max_weight, "cash_weight": config.cash_weight, "cost_bps": config.commission_bps + config.slippage_bps, "fx": "not hedged; prices are compared in native quote currencies and therefore are a research proxy"},
        "strategies": {"equal_weight_common_dates": {"metrics": metrics(equal_weight)}, "pure_momentum": {"metrics": metrics(pure.metrics), "rebalance_count": len(pure.rebalances), "average_turnover": sum(pure.turnover) / len(pure.turnover)}, "defended_rotation": {"metrics": metrics(defended.metrics), "rebalance_count": len(defended.rebalances), "average_turnover": sum(defended.turnover) / len(defended.turnover)}},
        "limitations": ["Six ETF sample is not a complete global asset universe.", "No FX conversion or hedging is applied; native-currency equal weighting is not investable portfolio accounting.", "No realtime, bid/ask, depth or order-level data is used.", "This research strategy is separate from the HK competition strategy and does not establish competition eligibility."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md = args.output.with_suffix(".md")
    lines = ["# 全球 ETF 多资产轮动基线", "", f"- 快照：{report['as_of']}", f"- 共同样本：{report['common_sample']['start']} 至 {report['common_sample']['end']}，{report['common_sample']['rows']} 个交易日", "", "| 策略 | 累计收益 | Sharpe | 最大回撤 | 平均换手 |", "|---|---:|---:|---:|---:|"]
    for name, item in report["strategies"].items():
        value = item["metrics"]
        lines.append(f"| {name} | {value['cumulative_return']:.2%} | {value['sharpe']:.2f} | {value['max_drawdown']:.2%} | {item.get('average_turnover', 0):.2%} |")
    lines.extend(["", "## 限制", ""] + [f"- {value}" for value in report["limitations"]] + [""])
    md.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report["strategies"], ensure_ascii=False, indent=2))
    print(f"WROTE {args.output}")
    print(f"WROTE {md}")


if __name__ == "__main__":
    main()
