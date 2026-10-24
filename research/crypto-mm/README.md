# Crypto market-making research

[简体中文](README.zh-CN.md)

An offline event-driven simulator for visible order-book queues, public trades and funding signals. B0 uses inventory-skewed quotes, B1 adds imbalance, B2 adjusts spreads using volatility, and B3 adds a funding-aware inventory target. See [assumptions](docs/assumptions.md) before interpreting results.

## Quick start

[Weekly daily-price research](../../docs/research/incremental-research.md) compares less frequent trend trading with calendar and exposure controls. It is separate from the maker-event simulator and requires a one-time reservation for real historical runs.

Hourly factor diagnostics are a separate offline CLI, `python -m crypto_mm.factors --spec /absolute/private/factor-protocol.json --output-root /absolute/data/new-factor-run`. They need an immutable hourly manifest and matching frozen source files. The root `team factors` command invokes the installed CLI without provider credentials. See [definitions and limits](../../docs/research/strategies.md#hourly-dex-factors) and [data setup](../../docs/research/datasets.md#dexpaprika-hourly-pilot). Synthetic delivery passes; the 2026-10-22 real-data check returned HTTP403 and produced no market observations or factor results.

From this directory, first configure an external `DATA_ROOT` and `UV_PROJECT_ENVIRONMENT`, then run:

```sh
uv sync --locked --group dev
uv run --locked python -m crypto_mm.demo
uv run --locked python -m crypto_mm.commands.audit_data --json
uv run --locked python -m crypto_mm.commands.backtest_cli --strategy B0 --days 2026-03-19
uv run --locked python -m crypto_mm.research.analyze_signals --days 2026-03-19
uv run --locked python -m crypto_mm.commands.plot_results
uv run --locked pytest -q
uv run --locked ruff check .
```

The demo writes nine Parquet files under `raw_data/{orderbook,trades,fundings}/` and a sibling `demo-manifest.json`. Each file is named `YYYY-MM-DD.parquet`. The current reader requires exactly the three configured date labels, `2026-03-19` through `2026-03-21`; they are fixture labels, not supplied historical observations. It normalizes datetime storage units to nanosecond events and reads `datetime`, 20 `bid_price_N`/`ask_price_N`/`bid_qty_N`/`ask_qty_N` book levels, trade `price`/`size`/`is_maker_ask`, and `funding_rate`. See `market_data.py` and `demo.py` for types and generated examples.

Backtest and analysis commands print to stdout. Plotting writes to the external project `figures/` directory and runs all four variants. It supports `--help` and rejects unknown arguments before plotting. No other plotting CLI options are provided; use `generate_figures(output_directory=...)` for an explicit destination. Sensitivity flags are exploratory reruns, not a parameter optimization guarantee. Inspect `StrategyConfig` and `SimulationConfig` in `config.py` for programmatic configuration and validation.

## Daily workflow modules

Daily price validation lives in `crypto_mm.data.daily_prices`, historical trend definitions in `crypto_mm.signals.daily_trend`, and target/calendar policies in `crypto_mm.portfolio`. Existing public helper imports from `crypto_mm.daily` modules remain available. The unchanged daily cash ledger consumes those targets, while the event-driven maker simulator retains its own model.

The optional [offline workflow check](../../docs/operations/workflow-check.md) runs fictional daily inputs through the installed policy and ledger, then verifies root-consumed artifacts, price/cost explanations and an immutable experiment record. These are engineering checks. Existing research protocols and published results remain unchanged.

## Known limitations

The separate `crypto_mm.daily` CLI consumes checked spot-daily manifests and supports `equal_weight` buy/hold and lagged `momentum_63d` diagnostics. It uses a 365-day calendar, explicit USDT quotes and traded-notional costs; it does not reuse the event receipt or simulate market making. See [dataset preparation](../../docs/research/datasets.md) and [new evaluation evidence](../../docs/research/data-expansion-and-evaluation.md). `python -m crypto_mm.daily --help` needs no workspace configuration.

Signal horizons use elapsed seconds. The sampling interval must exactly divide the 1, 5 and 30 second horizons; unrepresentable grids raise `ValueError`. The legacy `one_second_log_return` column retains its name but contains adjacent-grid log returns when the interval differs from one second. Timing and window settings require integers.

Audit quality adds `nonfinite_values` and book `nonpositive_price_rows` counts. Null counts remain separate; audit reports diagnose invalid input rather than certify exchange validity. Peak inventory includes individual fills within a timestamp batch. The linked evaluation records bounded three-day archived reruns, not a complete historical study or parameter optimization. Shared visible queues across overlapping orders and exchange-specific fill realism remain modeling limitations.

## Configuration and outputs

Use Python 3.12. Set `DATA_ROOT` to an absolute shared data directory before importing the package. It resolves to `DATA_ROOT/2026-quant-competition/research/crypto-mm/`. Alternatively set `WORKSPACE_CONFIG` to a TOML file containing an absolute `data_root`. Discovery then checks `CONFIG_ROOT/shared/workspace.toml`, or `XDG_CONFIG_HOME/quant-competition/shared/workspace.toml` (default `~/.config/quant-competition/shared/workspace.toml`). An explicit `DATA_ROOT` takes precedence. Missing or invalid settings raise an error, including for commands that import configuration before parsing `--help`.

Keep virtual environments, inputs, reports, charts and model outputs outside the checkout. For uv, set `UV_PROJECT_ENVIRONMENT` to an external environment path. Demo generation refuses to replace existing data. Demo numbers are fictional software fixtures and provide no investment or competition performance evidence.

## License and execution boundary

Code in this subtree is MIT licensed. This does not change the licensing of the rest of the repository or dependencies. No broker connections or order submission are provided. Research output is not `targets.json` and cannot be submitted directly to the execution runner. The published execution v1 JSON schema accepts JP/US. Runtime market normalization also recognizes HK, an existing schema/runtime inconsistency; crypto is not supported. Neither behavior makes these reports executable targets. A separate reviewed handoff adapter and execution validation would be needed. Competition product eligibility depends on official rules and broker/account permissions.

## Input and experiment acceptance

The opt-in [research acceptance tools](../../docs/research/research-acceptance.md) inspect explicit manifests and issue input receipts. These new entry points do not require global data configuration. Successful software checks do not establish research eligibility; owner provenance and holdout protocol validation remain unavailable. Default strategies and existing reports are preserved.

[Retrospective daily study](../../docs/research/real-data-study.md)
