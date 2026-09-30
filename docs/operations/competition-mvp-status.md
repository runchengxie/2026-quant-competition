# Competition Execution MVP Status

Last updated: 2026-09-30

> This execution MVP still uses Hong Kong equities as a test candidate. It does not mean the competition strategy has been selected or registered. The team is also comparing an AIVIX-driven U.S. ETF candidate. Current competition dates follow the organizer's 2026-09-23 public rules; historical backtest snapshot dates remain unchanged.

## Completed

- Collaboration requirements are recorded in the root `AGENTS.md`: isolated worktree, feature branch, pull request, merge, and cleanup.
- A Paper-safe competition configuration is available at `config/competition-2026-hk.json`.
- Basic Hong Kong market contracts support `HK / SEHK / HKD`.
- The system plans BUY/SELL deltas between target holdings and current positions.
- `run_target_rebalance_pipeline` connects target handoff, delta planning, and Paper/dry-run execution.
- Frozen runs support targets, lineage, resolved configuration, metrics, and evidence files.
- IBKR Hong Kong contract mapping and intent-direction submission are implemented.
- Paper-safe preflight checks Paper/dry-run mode, target handoff, single-name weights, dry-run rebalancing, and optional Gateway TCP reachability. See [Paper preflight](paper-preflight.md).
- A low-frequency Hong Kong momentum and volatility baseline compares 2800 buy-and-hold, pure momentum, and momentum with volatility control. Results are recorded in [the 2026-09-10 baseline](hk-strategy-baseline-2026-09-10.md).
- That historical baseline used daily snapshots for 20 Hong Kong stocks, monthly rebalancing, 10 holdings, 2% cash, a 12% single-name cap, and only data available before each rebalance close.

## Incomplete

- No full Paper Gateway smoke test has been completed for connection, contract qualification, order acknowledgments, cancellation, reconnect, or reconciliation.
- The preflight Gateway check is only a TCP probe; it is not a Paper API smoke test and does not confirm market-data permission or fills.
- Per-stock board lots, trading sessions, price bands, and liquidity limits still need confirmation from IBKR and the organizer; the configuration currently contains baseline assumptions.
- Competition `targets.json`, `lineage.json`, and a frozen out-of-sample performance run have not been imported from the research system.
- The organizer's calculation conventions for benchmark, position rate, turnover, and stability still need written confirmation.
- Continuous Paper shadow operation and daily reproducible performance reports have not been completed.
- The historical baseline is not a complete competition universe and does not prove Hong Kong real-time market-data permission. Historical and delayed data are the confirmed state.
- A resident NautilusTrader runtime and Gateway callback wiring remain follow-up integration work outside this broker-neutral MVP.

## Operating constraints

- Keep `environment=paper` and `dry_run=true`.
- Never commit `.env.local`, credentials, account information, order logs, or run artifacts.
- Until the Paper smoke test is complete, do not enable a live guard or describe results as verified broker execution.
