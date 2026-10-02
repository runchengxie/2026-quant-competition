# Local execution readiness — 2026-10-02

Baseline: main at `a5f5720`. This is a local software check, not a strategy performance validation.

## Results

- Relevant strategy, preflight and rebalance tests: **14 passed**.
- Real global ETF baseline: blocked because the expected historical CSV files are unavailable on this machine. No real-market performance result was produced.
- Six synthetic ETF series successfully exercised the existing backtest CLI. Synthetic performance metrics must not be presented as market evidence.
- A separate synthetic v1 Hong Kong target artifact passed target validation, weight limits and dry-run rebalancing: 10 intents, no broker submission attempted.
- The configured local Paper Gateway TCP endpoint was reachable. No IBKR API handshake, contract qualification, market-data entitlement, order acknowledgment or fill was verified.
- Backtest and execution preflight are separate probes: they are not an end-to-end signal-to-order strategy run. AIVIX, Index One and QuantZone signals were not used.
- The international v2 contract remains in a separate, unmerged development worktree. This check uses main's v1 execution path only.

Local inputs and reports are stored under the ignored `runs/readiness-2026-10-02/` directory. The synthetic target quantities are test inputs, not capital-sized orders.

## QuantZone configuration

`QUANTZONE_API_KEY` was absent from the example and local configuration. Both now reserve an empty value, alongside the candidate service URL. A real key must be supplied privately. No SDK, adapter or speculative authentication request was added.

## Code size

No cloc dependency, script or CI integration was configured previously. This check used the official standalone cloc 2.10 tool locally and Git-tracked file lists, excluding lockfiles. Worktrees, dependencies, credentials and run artifacts are excluded.

| Scope | Code lines (excluding blank/comment lines) |
| --- | ---: |
| Python application source (`src/`) | 2,556 |
| Python tests (`tests/`) | 1,305 |
| Site source and package manifest (`site/`) | 360 |
| All tracked files, including Markdown and configuration | 6,207 |

These counts describe the baseline commit before this report was added. The all-files count includes prose and is not an application source-code count. Counts are locally reproducible with `cloc --list-file=<git-tracked-files.txt> --json`; omit `uv.lock` and `site/package-lock.json` from the list.

## Next requirements

1. Locate or acquire licensed historical ETF/stock/futures and FX data; confirm adjustment and point-in-time semantics.
2. Validate provider responses, then connect a chosen strategy to target generation with reproducible lineage.
3. Complete and review the international v2 boundary before implementing international execution.
4. Validate IBKR Paper API and contract permissions before supervised order lifecycle testing.
