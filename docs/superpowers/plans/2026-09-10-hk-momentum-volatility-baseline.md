# Hong Kong Momentum and Volatility Baseline: Historical Plan

> This plan records the approach used for the 2026-09-10 baseline. It is research documentation, not the selected competition strategy.

**Goal:** Build an auditable low-frequency Hong Kong momentum and volatility-control baseline from available daily data and compare it with 2800 buy-and-hold and pure momentum.

**Architecture:** Keep research in the existing `strategies/international_lite` boundary and add a CSV-based Hong Kong portfolio backtest. The execution side remains Paper-first with `dry_run=true`; research backtests do not connect to order submission. Use a fixed data snapshot, lagged signals, explicit costs, and competition diagnostics.

**Stack:** Python 3.12 standard library, pytest, existing `strategies.international_lite` modules, and daily CSV inputs from the audited Hong Kong stock and 2800 snapshots.

## Constraints

- Use only stored Hong Kong daily data that passed basic quality checks; do not claim PIT fundamentals, real-time, Level 1/2, or order-book data.
- Long-only Hong Kong equities; no leverage, shorting, futures, options, or depth signals.
- Rebalance monthly. Signals use only closes known before the rebalance; holding-period returns begin on the next trading day.
- Defaults: 10 names, 12% single-name cap, 2% cash; all parameters configurable.
- Report gross/net returns, costs, turnover, position rate, flat days, and competition diagnostics without claiming award eligibility.
- Do not change IBKR account, order, or live-data permissions; execution remains Paper and dry-run.

## Planned tasks

1. Define daily-bar input and typed backtest interface; test CSV parsing, sorting, missing closes, look-ahead, and empty universe.
2. Implement momentum/volatility ranking, monthly selection, portfolio caps, and turnover buffers.
3. Add benchmark alignment, transaction costs, metrics, and reproducible report output.
4. Run focused and strategy test suites; record the sample and limitations.
