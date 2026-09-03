# International-lite strategy direction

The Windows-side strategy is a competition-oriented price/volume baseline,
not a replacement for the full Linux Nira research model. It uses only daily
bars that can be obtained and validated through the execution data path:
momentum, realized volatility, average volume and a deterministic score.

The objective is multi-dimensional because the competition evaluates
cumulative return, Sharpe, maximum drawdown and stability, while also imposing
holding-rate or turnover eligibility constraints. Therefore the baseline
should prefer liquid instruments, persistent positions and low-noise
rebalances over maximizing raw backtest return.

The implementation exposes `evaluate_competition_metrics` for the four core
diagnostics. Official ranking remains relative and cannot be reproduced from
local returns alone, so these metrics are guardrails rather than an invented
official score.

Recommended progression:

1. Start with liquid ETFs and a small top-k universe.
2. Use daily or weekly rebalance plus entry/exit buffers to avoid unnecessary
   turnover.
3. Keep a cash buffer and include FX, commissions and realistic slippage.
4. Validate at least the complete three-month competition window and multiple
   walk-forward windows before enabling any non-dry-run submission.
