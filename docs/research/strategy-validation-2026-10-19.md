# Strategy inventory and validation — 2026-10-19

The existing implementations run as offline experiments, but the four providers and IB Gateway do not currently form a complete data-to-order system. This snapshot contains 24 fixed-configuration diagnostics: eight equity-lab strategies on each of two small market inputs, two HK monthly variants, two five-region ETF variants, and four archived crypto maker replays. No competition strategy is selected. No order method was called.

English is canonical. [简体中文](strategy-validation-2026-10-19.zh-CN.md). The [reviewed aggregate snapshot](../../site/src/data/strategy-validation.json) supplies both language versions of Pages. It contains no raw observations, local paths, account/order identifiers or credentials. Calculation code was frozen at `ca6f4bc6f13fa933594cfe3f1823d800b42bb930`. This is exploratory software/model evidence, not an investable or out-of-sample track record.

## Implemented strategies and ideas

| Family | Actual implementation | Inputs and meaning |
| --- | --- | --- |
| HK monthly baseline | `hk_pure_momentum`, `hk_momentum_volatility` | Monthly prior-date rankings from 126/252-session momentum; the second adds volatility normalization. Position/cash caps remain the packaged defaults. This run has only one available stock, so it cannot validate cross-sectional selection. |
| Equity lab, HK or US | `sma_cross`, `momentum_20d` | Long-only 20/60 moving-average crossover and 20-session momentum. |
| Equity lab controls | `equal_weight`, `random_turnover` | Equal-weight and seeded random-selection controls. With one eligible asset they coincide; that is not independent alpha evidence. |
| Equity lab neural experiments | `cnn_pattern`, `cnn_pattern_mvp`, `cnn_image_pattern` | Experimental numeric/image CNN classifiers. Models can predict into training periods; full-period returns below include that risk. Names do not establish a paper replication. |
| Equity lab chronological model | `cnn_walk_forward_rank` | Date-based training/validation/test windows, purging and embargo, probability calibration and ranking. Unchanged 1,260-session training window exceeds this sample; there are no eligible folds. |
| Regional ETF rotation | `global_pure_momentum`, `global_defended_rotation` | Monthly 63/126/252-session momentum, with volatility/absolute-momentum defense in the second variant. Five available regions, not the original complete six-region universe. |
| Crypto maker B0 | Midpoint, fixed spread, inventory skew | Venue book/trade events and an inventory account. |
| Crypto maker B1 | L1 microprice/imbalance fair price | Same simulator, not a new exchange connection. |
| Crypto maker B2 | Volatility-adaptive spread | Historical volatility changes spread width. |
| Crypto maker B3 | Funding-aware inventory target | Rolling funding observations change desired inventory. They are not authenticated settlement/payment records. |
| Candidate only | AIVIX-driven US allocation; external HK XGBoost/PIT ranker | No completed end-to-end implementation in this repository. `international_lite` supplies reusable feature/evaluation helpers; Nira supplies handoff validation, not the external alpha model. Neither is another delivered autonomous strategy. |

## Provider and Gateway evidence

| Source | Actual evidence | What remains missing |
| --- | --- | --- |
| AIVIX / Cryptoracle | Current daily token discovery returned business code 200 after one direct-network retry. A frozen snapshot contains 2,280 BTC/ETH observations across three daily indicators. | Historical first-publication timestamps and revision policy are unknown. Stored periods retain timezone offsets; no causal equity overlay is validated. No equity prices or crypto L2. |
| Index One | Current public schema request returned HTTP 200 after one direct retry. Earlier bounded FX execution worked. | Equity/ETF history and portfolio reconciliation are unverified. Previously retrieved low-precision HKD FX is unsuitable for precise valuation. Schema discovery is not an authenticated equity entitlement test. |
| Algoseek | Official API describes US equities/options/futures and reference data. | No authorized configuration or local dataset was established in this task. No authenticated call, purchase or download was attempted. No HK coverage is established. |
| CoinPaprika | Current BTC/ETH latest OHLCV each returned HTTP 200 and one candle. Stored daily ticker histories contain 365 points each. | Ticker price/24-hour-volume histories are not exchange OHLCV or depth/trade sequences. Earlier deep OHLCV request was restricted. They cannot drive this maker simulator. |
| IB Gateway | Current read-only handshake succeeded. One HK stock returned 738 daily bars through 2026-10-16. A second contract failed qualification; error 1100 then interrupted collection. One reconnection was refused. | Complete current stock coverage, persistent connectivity, real-time subscriptions and account/product execution permissions. Configured Paper port alone does not prove account mode. |

Provider responses and account synchronization were kept private. No order methods, account settings, subscriptions, storage/deployment workflows or production data pointers were changed. Discovery probes and backtests are separate checks. None proves a supervised order lifecycle or the research-to-broker connection.

Official references: [Cryptoracle token discovery](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1/api-list/co-private-data/token-list), [Index One API](https://indexone.io/docs/api), [Algoseek datasets API](https://algoseek.com/docs/rest-api/intro), [CoinPaprika API](https://coinpaprika.com/api/developers/). Product documentation does not establish this account's entitlements.

## Inputs, assumptions and interpretation

Equity-lab HK uses one stock, `HK.5`, with `HK.2800` only as benchmark. US uses `US.SPY` only. The stock sample is 2023-10-18–2026-09-30, 727 aligned sessions; US is 2023-10-03–2026-09-30, 751 sessions. Frozen ETF OHLCV came from prior IBKR TRADES/RTH collection. The common analytical cutoff is 2026-09-30; later freshly retrieved HK bars were excluded from these experiments. No OHLC bars were synthesized from CoinPaprika ticker prices.

All eight equity strategies retain packaged signal/model configurations and seeds. Backtest overrides are initial capital 100,000 in local quote units, daily rebalance, benchmark calendar, commission 8 bps, slippage 12 bps, and regulation 10 bps for HK or zero for US. Costs are illustrative constants per traded notional, not verified current IBKR fees. Risk limits differ by packaged strategy. Next-period signal shifting does not eliminate CNN training leakage. Daily target-weight accounting, unverified adjustments/dividends, fixed current universe, small sample breadth and fill proxies prevent an investment-performance claim. Single-asset buy-and-hold-like controls can substantially outperform capped signal strategies because exposure differs.

The HK monthly sample starts after warmup on 2024-11-01, 471 observations, with 10 bps costs and the original cash/position caps. The five-region ETF sample starts 2024-12-02, 423 common-date observations, with 10 bps costs. It omits Canada due missing permitted history, compares native-currency price returns, and retains the legacy 252-period Sharpe convention. FX, dividends, synchronized venue marks and a fully self-financing holdings ledger are not implemented by these legacy functions. Do not compare these figures directly with equity-lab results.

Crypto uses a separate archived event sample dated 2026-03-19–21, not data acquired from the four named providers. All nine file hashes matched the retained manifest. Recorded audits found no flagged null/non-finite values, ordering defects, nonpositive prices/quantities or duplicate trades under their checks. The files contain 3,581,577 book snapshots, 70,556 trades and 12,902 funding observations. Venue, instrument and timezone provenance remain unauthenticated; a quality scan cannot establish them. Timestamps are treated as UTC by the existing simulator.

B0–B3 use unchanged defaults: tick 0.1, order quantity 0.1, inventory limit 1, placement/cancellation latency 100 ms, maker fee zero, and one-second snapshots. There is no funded-capital return denominator or verified quote-currency identity, so crypto results are absolute PnL in source quote units, not percent returns or Sharpe. The sample does not prove fillability, queue realism or generalization. Same-price overlapping queues remain a model limitation. The archived replay is not a verified historical trading record.

`completed` in a research summary only means the function returned. This publication independently labels no-position outputs `no_trades` and the walk-forward result `no_eligible_folds`, whose performance cells are null. No hyperparameter search, shortened training window or alternative test expectation was used to make these results look successful. Maximum drawdown in the public equity tables is a positive magnitude.

## Results


### HK

| strategy | start / end | return | Sharpe | drawdown | evidence |
| --- | --- | ---: | ---: | ---: | --- |
| `cnn_image_pattern` | 2023-10-18 / 2026-09-30 | 22.77% | 1.539 | 4.65% | `in_sample_diagnostic` |
| `cnn_pattern` | 2023-10-18 / 2026-09-30 | 0.00% | N/A | 0.00% | `no_trades` |
| `cnn_pattern_mvp` | 2023-10-18 / 2026-09-30 | 22.77% | 1.539 | 4.65% | `in_sample_diagnostic` |
| `cnn_walk_forward_rank` | 2023-10-18 / 2026-09-30 | N/A | N/A | N/A | `no_eligible_folds` |
| `equal_weight` | 2023-10-18 / 2026-09-30 | 152.99% | 1.479 | 22.12% | `limited_universe` |
| `momentum_20d` | 2023-10-18 / 2026-09-30 | 6.91% | 0.717 | 3.84% | `limited_universe` |
| `random_turnover` | 2023-10-18 / 2026-09-30 | 152.99% | 1.479 | 22.12% | `limited_universe` |
| `sma_cross` | 2023-10-18 / 2026-09-30 | 13.62% | 1.068 | 4.65% | `limited_universe` |
| `hk_pure_momentum` | 2024-11-01 / 2026-09-30 | 10.60% | 1.758 | 2.81% | `limited_universe` |
| `hk_momentum_volatility` | 2024-11-01 / 2026-09-30 | 10.60% | 1.758 | 2.81% | `limited_universe` |

### US

| strategy | start / end | return | Sharpe | drawdown | evidence |
| --- | --- | ---: | ---: | ---: | --- |
| `cnn_image_pattern` | 2023-10-03 / 2026-09-30 | 13.30% | 1.395 | 4.04% | `in_sample_diagnostic` |
| `cnn_pattern` | 2023-10-03 / 2026-09-30 | 0.00% | N/A | 0.00% | `no_trades` |
| `cnn_pattern_mvp` | 2023-10-03 / 2026-09-30 | 13.30% | 1.395 | 4.04% | `in_sample_diagnostic` |
| `cnn_walk_forward_rank` | 2023-10-03 / 2026-09-30 | N/A | N/A | N/A | `no_eligible_folds` |
| `equal_weight` | 2023-10-03 / 2026-09-30 | 80.53% | 1.373 | 19.00% | `limited_universe` |
| `momentum_20d` | 2023-10-03 / 2026-09-30 | 5.63% | 0.966 | 1.91% | `limited_universe` |
| `random_turnover` | 2023-10-03 / 2026-09-30 | 80.53% | 1.373 | 19.00% | `limited_universe` |
| `sma_cross` | 2023-10-03 / 2026-09-30 | 6.00% | 0.934 | 2.07% | `limited_universe` |

### MULTI

| strategy | start / end | return | Sharpe | drawdown | evidence |
| --- | --- | ---: | ---: | ---: | --- |
| `global_pure_momentum` | 2024-12-02 / 2026-09-30 | 31.95% | 1.436 | 12.71% | `native_currency_proxy` |
| `global_defended_rotation` | 2024-12-02 / 2026-09-30 | 31.60% | 1.470 | 12.71% | `native_currency_proxy` |

### CRYPTO

| strategy | PnL | fills | peak inventory | evidence |
| --- | ---: | ---: | ---: | --- |
| `B0` | -235.370 | 5400 | 1.000 | `archived_diagnostic` |
| `B1` | -240.258 | 4939 | 1.000 | `archived_diagnostic` |
| `B2` | -6.684 | 463 | 0.738 | `archived_diagnostic` |
| `B3` | -256.235 | 5386 | 1.000 | `archived_diagnostic` |

All four crypto variants lose money under this particular zero-fee model and sample. Lower loss in B2 does not prove a durable advantage.

## Reproduction and remaining work

Install each package with its own committed lockfile. Set an external `DATA_ROOT` and `UV_PROJECT_ENVIRONMENT`. Use licensed inputs and explicit config/universe files; provider snapshots are not bundled. The standard equity command is `python -m equity_lab.cli backtest --strategy <name> --root <external-run-root> --config <backtest.yaml> --universe <universe.txt>`. Set a distinct `report_path` per strategy. Keep the exact packaged strategy YAML, costs and date cutoff described above.

For crypto, use the existing API with an explicit data path: `crypto_mm.backtest.run_backtest(strategy_id="B0", data_root=Path("<licensed-event-directory>"))`, repeat for B1/B2/B3, and retain `dataclasses.asdict(result)`. Each package also supports its documented synthetic demo, which is a different input class. Monthly research functions are `strategies.hk_low_frequency.run_monthly_backtest` and `strategies.global_etf_rotation.run_monthly_rotation`.

The JSON records input/config SHA-256 fingerprints and code revision. Input fingerprints hash the sorted source file hashes; equity source manifests additionally retain normalization/filter lineage privately. Equity config fingerprints cover packaged strategy YAML and path-free backtest overrides; monthly fingerprints reference fixed source defaults at the recorded revision. Crypto fingerprints cover the full returned config. Observations mean aligned sessions for daily strategies and input events for crypto. Public aggregates can be inspected without receiving restricted raw data; reproducing identical results requires the same authorized snapshots.

Next steps: restore Gateway connectivity and obtain a complete PIT/adjustment-aware stock universe; establish Algoseek entitlement; confirm AIVIX first-availability/revision semantics before an overlay; validate Index One security coverage and precision; authenticate venue/product event lineage and fees; obtain enough chronological history for neural out-of-sample testing. Research packages have no broker wiring. HK v1 schema alignment, client/broker ID mapping, account mode and supervised Paper order/ack/cancel/fill/restart/reconciliation remain unresolved.
