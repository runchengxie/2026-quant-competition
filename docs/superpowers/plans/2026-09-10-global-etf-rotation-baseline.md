# Global ETF Rotation Baseline: Historical Plan

> This plan records the approach for the 2026-09-10 research baseline. The strategy is separate from the Hong Kong competition strategy.

**Goal:** Build an auditable multi-market ETF rotation baseline from six stored daily ETF series and compare it with buy-and-hold and pure momentum.

**Architecture:** Add a separate `strategies/global_etf_rotation` module without changing the Hong Kong candidate. Form monthly signals using common trading dates, 3/6/12-month momentum, and 60-day volatility. Hold Top-K assets; move to cash when absolute-momentum or risk conditions fail. Report currency, calendar, and data-coverage limitations.

**Stack:** Python 3.12 standard library, pytest, existing competition metrics, and stored daily ETF CSVs.

## Constraints

- Use only SPY, 2800, ISF, STW, XIU, and ES3 daily close/volume in the recorded snapshot.
- No real-time data, order book, leverage, shorting, or order submission. This is separate research and does not replace the Hong Kong configuration.
- Rebalance monthly using data available before the signal date. Use common dates; do not forward-fill beyond the next common date.
- Default to at most three ETFs, a 45% single-name cap, and at least 10% cash; all settings are configurable.
- Record source snapshot, asset count, common dates, currency/FX limits, costs, and comparison metrics.

## Planned tasks

1. Add daily ETF input and strategy interfaces; test parsing, common-date alignment, look-ahead, and empty-history handling.
2. Implement momentum, volatility, and cash-defensive selection.
3. Add benchmark alignment, costs, metrics, and report output.
4. Run focused tests and record the limitations of the research result.
