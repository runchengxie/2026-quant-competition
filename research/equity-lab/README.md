# Offline equity research

[简体中文](README.zh-CN.md)

A daily CSV/YAML backtest laboratory with eight offline strategies: `sma_cross`, `momentum_20d`, `equal_weight`, `random_turnover`, `cnn_pattern`, `cnn_pattern_mvp`, `cnn_image_pattern`, and `cnn_walk_forward_rank`. CNN names describe experimental implementations, not independently validated paper replications. No Futu/OpenD SDK, account code, online sentiment provider or execution adapter is included.

## Quick start

From this directory, configure external `DATA_ROOT` and `UV_PROJECT_ENVIRONMENT`, then run:

```sh
uv sync --locked --group dev
uv run --locked python -m equity_lab.cli list
uv run --locked python -m equity_lab.cli demo
uv run --locked python -m equity_lab.cli backtest --strategy equal_weight
uv run --locked pytest -q
uv run --locked ruff check .
```

Demo symbols `HK.DEMO_A` and `HK.DEMO_B` are fictional. The generated 90 business-day bars are not an exchange calendar or market history. CSV columns are `date,open,high,low,close,volume,code`; filenames replace dots in codes with underscores. Daily bars live at `artifacts/data/processed/market/` below the external project root.

`backtest` accepts `--root`, `--config`, `--strategy-config`, and `--universe`. Relative price/report paths in backtest YAML resolve against `--root`, not the checkout. Absolute paths are accepted. Without explicit files, `root/config/` is used when present, otherwise packaged templates are used. Environment overrides are `EQUITY_LAB_BACKTEST_CONFIG`, `EQUITY_LAB_STRATEGY_CONFIG`, and `EQUITY_LAB_UNIVERSE_FILE`. The Python service also accepts `compare_benchmarks` and `benchmark_list`. Templates use illustrative constant costs, not verified current fees.

Outputs include `portfolio_daily.csv`, `positions_daily.csv`, `summary.json`, `monthly_returns.csv`, `drawdown_daily.csv` and an optional `equity_curve.png`, normally under `artifacts/reports/backtests/`. Walk-forward/decile and comparison artifacts are conditional. Reports include configuration/data metadata and may contain absolute custom paths or exception messages. Review them before sharing.

## Interpretation and limitations

This is a daily fractional-weight proxy with lagged exposures and close-to-close returns. It does not model HK board lots, auctions, realistic fills, minimum commissions, FX conversion, or broker-specific permissions. Metrics annualize using 252 days. Missing bars can be forward-filled, and calendar configuration can fall back to the observed date union. Data quality flags do not automatically enforce exchange tradability. Adjusted-price/dividend inputs require review to avoid duplicate distributions. Survivorship, delisting and model selection biases are not automatically resolved. Walk-forward metadata contains fixed window assumptions and is not proof that every custom configuration is validated.

If signal construction raises, the inherited service keeps an all-cash fallback. `summary.json` now exposes `run_status=strategy_fallback` and `fallback_reasons`; the CLI prints them and exits with status 2. Such output is a failed strategy run, not a successful zero-return strategy. Ordinary runs use `run_status=completed`, which does not establish research validity. Relative metadata paths use `/` across platforms.


Filled-close provenance is recorded before forward filling: `is_missing_bar` describes missing open/close inputs, `is_interpolated` marks filled closes, and `is_halt` remains a zero-volume proxy rather than confirmed exchange status. Costs prefer explicit strategy `market`, then backtest `market`, then benchmark/universe inference. Baseline comparison directories contain the portfolio and position CSVs declared in their summaries. `max_positions` limits desired selections; gradual turnover transitions can temporarily retain more realized holdings. Non-walk-forward CNN variants can include in-sample predictions and should not be presented as out-of-sample evidence.

## Configuration and outputs

Use Python 3.12. Set `DATA_ROOT` to an absolute shared data directory before importing the package. It resolves to `DATA_ROOT/2026-quant-competition/research/equity-lab/`. Alternatively set `WORKSPACE_CONFIG` to a TOML file containing an absolute `data_root`. Discovery then checks `CONFIG_ROOT/shared/workspace.toml`, or `XDG_CONFIG_HOME/quant-competition/shared/workspace.toml` (default `~/.config/quant-competition/shared/workspace.toml`). An explicit `DATA_ROOT` takes precedence. Missing or invalid settings raise an error, including for commands that import configuration before parsing `--help`.

Keep virtual environments, inputs, reports, charts and model outputs outside the checkout. For uv, set `UV_PROJECT_ENVIRONMENT` to an external environment path. Demo generation refuses to replace existing data. Demo numbers are fictional software fixtures and provide no investment or competition performance evidence.

## License and execution boundary

Code in this subtree is MIT licensed. This does not change the licensing of the rest of the repository or dependencies. No broker connections or order submission are provided. Research output is not `targets.json` and cannot be submitted directly to the execution runner. The published execution v1 JSON schema accepts JP/US. Runtime market normalization also recognizes HK, an existing schema/runtime inconsistency; crypto is not supported. Neither behavior makes these reports executable targets. A separate reviewed handoff adapter and execution validation would be needed. Competition product eligibility depends on official rules and broker/account permissions.
