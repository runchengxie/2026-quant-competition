from __future__ import annotations

from .services.backtest import run_backtest_service


def run_backtest(
    strategy_name: str = "sma_cross",
    *,
    compare_benchmarks: bool = False,
    benchmark_list: str | None = None,
) -> None:
    result = run_backtest_service(
        strategy_name,
        compare_benchmarks=compare_benchmarks,
        benchmark_list=benchmark_list,
    )
    print("Backtest finished.")
    print("Run status:", result.artifact_bundle["summary"]["run_status"])
    for reason in result.artifact_bundle["summary"]["fallback_reasons"]:
        print("Strategy failure:", reason)
    print("Strategy:", result.strategy_name)
    print("Strategy config:", result.strategy_config_path)
    print("Universe:", ", ".join(result.universe))
    print("Latest equity:", f"{result.latest_equity:.2f}")
    print("Total return:", f"{result.total_return:.2%}")
    print("Max drawdown:", f"{result.max_drawdown:.2%}")
    print("Portfolio report:", result.portfolio_path)
    print("Positions report:", result.positions_path)
    print("Summary report:", result.artifact_bundle["summary_path"])
    wf = result.artifact_bundle.get("comparison", {}).get("benchmark_count", 0) if isinstance(result.artifact_bundle.get("comparison"), dict) else 0
    if wf:
        print("Benchmark baselines:", wf)

    comparison = result.artifact_bundle.get("comparison") if isinstance(result.artifact_bundle, dict) else None
    if comparison:
        print("Benchmark comparison:")
        print("  path:", comparison.get("comparison_json"))


def main() -> None:
    import argparse
    from pathlib import Path
    from .demo import build_demo_data
    from .strategies import discover_strategy_names

    parser = argparse.ArgumentParser(description="Offline daily equity research")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List offline strategy modules")
    demo = commands.add_parser("demo", help="Create explicitly fictional local daily bars")
    demo.add_argument("--root", type=Path)
    backtest = commands.add_parser("backtest", help="Run a local CSV/YAML backtest")
    backtest.add_argument("--strategy", default="sma_cross", choices=discover_strategy_names())
    backtest.add_argument("--root", type=Path)
    backtest.add_argument("--config", type=Path)
    backtest.add_argument("--strategy-config", type=Path)
    backtest.add_argument("--universe", type=Path)
    args = parser.parse_args()
    if args.command == "list":
        print("\n".join(discover_strategy_names()))
    elif args.command == "demo":
        from .paths import PROJECT_ROOT
        for path in build_demo_data(args.root or PROJECT_ROOT):
            print("Synthetic demonstration:", path)
    else:
        result = run_backtest_service(args.strategy, root=args.root, config_path=args.config,
                                      strategy_config_path=args.strategy_config, universe_path=args.universe)
        summary = result.artifact_bundle["summary"]
        print("Run status:", summary["run_status"])
        print("Summary report:", result.artifact_bundle["summary_path"])
        if summary["run_status"] != "completed":
            for reason in summary["fallback_reasons"]:
                print("Strategy failure:", reason)
            raise SystemExit(2)


if __name__ == "__main__":
    main()
