# Expanded data and retrospective evaluation

[简体中文](data-expansion-and-evaluation.zh-CN.md)

The new work adds standalone dataset tools, a fixed eight-product crypto daily study, 30 equity rolling diagnostics and 12 fresh archived maker replays. It does not establish a historical S&P500 selection universe or an executable competition strategy. The original 24-result `strategy-validation.json` remains unchanged; new public facts live in `site/src/data/strategy-expansion.v1.json`.

## Data obtained and missing prerequisites

Binance spot monthly archives supplied 1,096 daily bars per product for 2023-01-01 through 2025-12-31: BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, ADAUSDT, DOGEUSDT and LINKUSDT. Total coverage is 8,768 bars. Every archive has a matching verified checksum; normalized daily bars have exact byte hashes and explicit UTC/USDT identity. A preliminary BTC/ETH three-month pilot obtained 92 bars each. All raw files and full receipts remain outside Git.

The broad request starts in 2016 and targets the latest completed month. It has separate checkpoints and missing archives, including periods before these venue products existed. The completed 2023–2025 study must not be described as complete 2016-to-present coverage. Neither the fixed eight-name pool nor the BTC/ETH subset is a historical PIT selection universe. Current candidate selection can introduce survivorship and selection bias; no historical volume eligibility or all-market claim is made.

Historical S&P500 membership and compatible price access remain missing. The inspected configuration did not provide an Algoseek key; provider documentation is not proof of entitlement. The configured Paper Gateway TCP endpoint was unreachable during this task, so no broker API login, startup, restart or new historical request was attempted. Existing single-instrument equity inputs remain usable diagnostics. The two HK monthly candidates lack the required multi-stock input set and were not rerun. Neural training defaults remain unchanged and no shortened neural run is presented.

See [dataset contracts and commands](datasets.md) for import formats, budgets, source support and partial states. The broker adapter currently implements only the bounded one-month read-only pilot; bulk broker expansion and authenticated vendor acquisition are not delivered capabilities.

The broad scan finished with 23,778 observed bars through 2026-09-30 and 256 unavailable/incomplete monthly chunks, so its status remains partial. Observed starts differ by product: BTC/ETH 2017-08-17, BNB 2017-11-06, XRP 2018-05-04, ADA 2018-04-17, LINK 2019-01-16, DOGE 2019-07-05 and SOL 2020-08-11. This larger retained dataset was not used to change the fixed 2023–2025 experiment windows.

## Daily crypto method and results

Both portfolios start with 63 observed days of warmup. The evaluated holding periods are 2023-03-05 through 2025-12-31, with 365 periods per year. Starting capital is normalized to 1 in the common USDT quote. This does not assume a stable USD exchange rate.

`equal_weight` buys equal allocations once and then holds the resulting quantities. `momentum_63d` selects products whose trailing 63-day close return is positive, allocates equally among them and otherwise holds cash. Each period uses only the previous close. Weights drift with prices between decisions; costs apply to absolute one-way traded notional, including initial entry. There is no forced terminal liquidation cost. Zero-cost runs and 10 bps runs change only costs; there is no parameter search.

| Pool | Strategy | Cost | Net return | Maximum drawdown |
| --- | --- | --- | --- | --- |
| BTC/ETH | equal_weight | 0 bps | 190.95% | 40.25% |
| BTC/ETH | equal_weight | 10 bps | 190.66% | 40.25% |
| BTC/ETH | momentum_63d | 0 bps | 161.63% | 38.16% |
| BTC/ETH | momentum_63d | 10 bps | 137.43% | 39.30% |
| Eight products | equal_weight | 0 bps | 200.29% | 50.08% |
| Eight products | equal_weight | 10 bps | 199.99% | 50.08% |
| Eight products | momentum_63d | 0 bps | 161.64% | 54.54% |
| Eight products | momentum_63d | 10 bps | 105.03% | 57.00% |

On this disclosed retrospective sample, the momentum rule did not improve net return over buy/hold. Turnover costs reduce it substantially, especially in the larger pool. These observations do not validate live profitability, liquidity/capacity, funding, venue eligibility or future performance. Daily bars cannot test maker execution.

## Equity rolling diagnostics

The existing engine and packaged `equal_weight`, `momentum_20d` and `sma_cross` defaults were retained. Each market uses five consecutive complete 63-session evaluation windows, each preceded by 252 warmup sessions. Positions carry from that window's warmup. The same market input, dates, universe and costs are used across strategies. There are 30 jobs in total; they completed in about 26 seconds.

HK uses one stock with a separate benchmark; US uses SPY alone. HK evaluation spans 2025-05-07 through 2026-08-13; US spans 2025-04-07 through 2026-07-09. Existing source hashes were checked before rerunning. Costs remain 30 bps in HK and 20 bps in US. Adjustment/corporate-action and publication timing have not been independently certified. Results remain in HKD and USD respectively, with 252-period annualization.

| Market | Strategy | Product of five fold return factors minus 1 |
| --- | --- | --- |
| HK | equal_weight | 87.01% |
| HK | momentum_20d | 5.33% |
| HK | sma_cross | 10.08% |
| US | equal_weight | 48.77% |
| US | momentum_20d | 2.35% |
| US | sma_cross | 3.80% |

This fold summary is not a continuously funded portfolio simulation or cross-sectional stock-selection result. Pages retains each fold's dates, net return and drawdown. Full private records also include turnover, exposure, source hashes and per-fold artifacts. Fewer than 252+63 valid common sessions produce no complete fold, not a fabricated zero-return success.

## Maker sensitivity

All B0–B3 strategies were rerun over the three archived dates 2026-03-19 through 21. The input files and engine source were fingerprinted. Twelve scenarios completed in about 25.7 minutes, within the 45-minute cap. Each strategy has its unchanged baseline, maker fee 1 bps and placement/cancellation latency 300 ms, with one factor changed per scenario.

| Strategy | Baseline PnL | Fee1bps PnL | Latency300ms PnL |
| --- | --- | --- | --- |
| B0 | -235.370 | -347.486 | -287.739 |
| B1 | -240.258 | -343.724 | -274.320 |
| B2 | -6.684 | -16.294 | -24.467 |
| B3 | -256.235 | -368.121 | -291.694 |

Venue, product identity and account currency remain unverified. These PnL figures are recorded account units, not USD values or returns with a funded denominator. B2 lost less in this small archive; that is not evidence of a robust profitable strategy. The current fill model has no conservative-fill control, so those four proposed cases are explicitly unsupported rather than simulated with a new model. No authenticated new L2 data or venue-specific execution validation was obtained.

## Reproduction and publication boundary

Use the [team quickstart](../operations/team-quickstart.md) and external configuration. An evaluation specification has `schema` equal to `competition.evaluation_spec.v1` and a `manifests` array of absolute dataset-manifest paths:

```sh
python team.py evaluate --config /absolute/private/team.toml --spec /absolute/private/evaluation.json --output-root /absolute/data/new-evaluation
```

This command currently dispatches the two daily crypto strategies at 0 and 10 bps in the separate crypto environment, up to 32 jobs and 1 hour. It does not run the equity or maker matrices. For an explicit BTC/ETH subset, run in the installed crypto environment:

```sh
python -m crypto_mm.daily --manifest /absolute/data/manifest.json --products BTCUSDT ETHUSDT --strategy momentum_63d --fee-bps 10 --output-root /absolute/data/new-btc-eth-run
```

Daily result files include the exact manifest hash, source-file hashes, method version, products, lag, costs, quote and per-period accounting. Output directories must be new and external. The existing equity service and maker `run_backtest` API performed the other matrices; exact private task drivers and receipts are retained externally because they reference local licensed inputs. To reproduce equity folds, prepare the stated common 315-session panels, use unchanged packaged strategies and the costs above, then score only the final 63 sessions. Maker replay uses `BacktestConfig` and `SimulationConfig` with only the stated scenario override.

The public projection explicitly selects dates, product IDs, coverage counts, methods, currencies, costs, scalar metrics and blocker codes. It excludes raw bars, book/trade observations, local paths, credential references, account identifiers and private reproduction locators. Both site languages render the same JSON. Every dataset and result remains outside `accepted_research`; the existing research gate is unchanged.
