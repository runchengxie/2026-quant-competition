# Crypto market-making research

[简体中文](README.zh-CN.md)

An offline event-driven simulator for visible order-book queues, public trades and funding signals. B0 uses inventory-skewed quotes, B1 adds imbalance, B2 adjusts spreads using volatility, and B3 adds a funding-aware inventory target. See [assumptions](docs/assumptions.md) before interpreting results.

## Quick start

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

The demo writes nine Parquet files under `raw_data/{orderbook,trades,fundings}/` and a sibling `demo-manifest.json`. Each file is named `YYYY-MM-DD.parquet`. The current reader requires exactly the three configured date labels, `2026-03-19` through `2026-03-21`; they are fixture labels, not supplied historical observations. It reads nanosecond `datetime`, 20 `bid_price_N`/`ask_price_N`/`bid_qty_N`/`ask_qty_N` book levels, trade `price`/`size`/`is_maker_ask`, and `funding_rate`. See `market_data.py` and `demo.py` for types and generated examples.

Backtest and analysis commands print to stdout. Plotting writes to the external project `figures/` directory and runs all four variants. It has no argument parser: arguments, including `--help`, are ignored and can trigger plotting. Sensitivity flags are exploratory reruns, not a parameter optimization guarantee. Inspect `StrategyConfig` and `SimulationConfig` in `config.py` for programmatic configuration and validation.

## Known limitations

Custom signal sampling intervals can produce incorrect horizon labels because horizons are interpreted as sample offsets. The data audit does not comprehensively reject NaN or infinity; an audit pass is not proof of valid numeric data. These inherited issues remain visible and are not repaired by changing test expectations. A full historical backtest or parameter scan has not been reproduced for this snapshot.

## Configuration and outputs

Use Python 3.12. Set `DATA_ROOT` to an absolute shared data directory before importing the package. It resolves to `DATA_ROOT/2026-quant-competition/research/crypto-mm/`. Alternatively set `WORKSPACE_CONFIG` to a TOML file containing an absolute `data_root`. Discovery then checks `CONFIG_ROOT/shared/workspace.toml`, or `XDG_CONFIG_HOME/quant-competition/shared/workspace.toml` (default `~/.config/quant-competition/shared/workspace.toml`). An explicit `DATA_ROOT` takes precedence. Missing or invalid settings raise an error, including for commands that import configuration before parsing `--help`.

Keep virtual environments, inputs, reports, charts and model outputs outside the checkout. For uv, set `UV_PROJECT_ENVIRONMENT` to an external environment path. Demo generation refuses to replace existing data. Demo numbers are fictional software fixtures and provide no investment or competition performance evidence.

## License and execution boundary

Code in this subtree is MIT licensed. This does not change the licensing of the rest of the repository or dependencies. No broker connections or order submission are provided. Research output is not `targets.json` and cannot be submitted directly to the execution runner. The published execution v1 JSON schema accepts JP/US. Runtime market normalization also recognizes HK, an existing schema/runtime inconsistency; crypto is not supported. Neither behavior makes these reports executable targets. A separate reviewed handoff adapter and execution validation would be needed. Competition product eligibility depends on official rules and broker/account permissions.
