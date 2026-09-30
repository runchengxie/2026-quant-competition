# Paper-Safe Execution Preflight

The preflight checks execution prerequisites only. It does not place or cancel orders. A successful TCP connection does not prove market-data permission or order execution.

## Usage

```powershell
uv run --extra test python scripts/run_paper_preflight.py `
  --targets path\to\targets.json `
  --config config\competition-2026-hk.json `
  --output runs\preflight.json
```

To additionally check TCP reachability of the local Paper Gateway, explicitly add:

```powershell
uv run python scripts/run_paper_preflight.py `
  --targets path\to\targets.json `
  --config config\competition-2026-hk.json `
  --check-gateway
```

## Checks

- `execution_safety`: requires `environment=paper` and `dry_run=true`; resolved environment overrides take precedence.
- `target_handoff`: validates `targets.json`, optional sibling `lineage.json`, market, and strategy identifiers.
- `target_risk`: checks the configured maximum single-name weight and total target weight.
- `dry_run_rebalance`: creates delta intents while `dry_run` prevents calls to a broker adapter.
- `gateway`: skipped by default. When requested, it performs only a TCP connection check and reports `blocked` if the endpoint is unavailable.

## Status values

- `pass`: the check passed.
- `fail`: an input or safety condition is not satisfied and should be fixed.
- `blocked`: an external prerequisite is unavailable, such as a Gateway that is not listening; this does not mean an order was rejected or market data is unauthorized.
- `skipped`: the check was not requested.

Keep the JSON report in a local `runs/` directory. Do not commit account details, credentials, order logs, or sensitive run artifacts.
