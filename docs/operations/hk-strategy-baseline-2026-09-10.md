# Hong Kong Low-Frequency Momentum and Volatility Baseline

- Snapshot date: 2026-09-10.
- Universe: 20 stocks, 2023-09-05 to 2026-09-03.
- Benchmark proxy: `HK_2800.csv`, 2023-09-05 to 2026-09-03.
- Assumed commission and slippage: 10.0 basis points combined.

## Comparison

| Portfolio | Cumulative return | Sharpe | Maximum drawdown | Positive-day share | Rebalances | Average rebalance turnover |
|---|---:|---:|---:|---:|---:|---:|
| 2800 buy and hold | 35.44% | 0.56 | 20.56% | 49.25% | 0 | 0.00% |
| Pure momentum | 21.33% | 0.52 | 23.93% | 49.89% | 24 | 34.30% |
| Momentum with volatility control | 33.99% | 0.76 | 19.87% | 52.22% | 24 | 30.22% |

## Interpretation and limitations

- Only 20 Hong Kong stocks are included; this is not a complete historical competition universe.
- No PIT constituents or fundamentals are used.
- No real-time, bid/ask, depth, tick, or order-level data is used.
- Daily-close execution is a research proxy and does not prove live fillability.
- Competition rule interpretations, benchmark, and turnover threshold still require organizer confirmation.

These results describe historical research on the available 20-stock daily snapshot only. They do not establish real-time market-data access or permission to place live orders.
