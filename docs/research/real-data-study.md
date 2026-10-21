# Retrospective daily study

This optional study compares fixed strategies on immutable daily snapshots. It is retrospective research with a fixed current pool, not a historical index reconstruction or an accepted execution strategy. Original engines, the 24-result snapshot and the expanded daily snapshot retain their original accounting and results.

## Inputs and strategies

Stock inputs require complete `competition.dataset_manifest.v2` IBKR daily snapshots, an exchange-session grid, USD for US or HKD for HK, and a separate SPY or 2800 benchmark. TRADES prices are split adjusted, not dividend total returns. The crypto path consumes Binance spot USDT daily candles. A partial parent archive is allowed only through a hash-bound, verified contiguous selected slice starting no earlier than 2023-01-01. This does not change the parent's partial status. No raw data is published.

| Market | Fixed strategies | One-way fee assumptions |
| --- | --- | --- |
| US | buy_hold, daily equal_weight, momentum_20d, sma_cross(20,60), SPY buy_hold | 20, 40 bps |
| HK | Same stock methods, 2800 buy_hold benchmark | 30, 60 bps |
| Crypto | buy/hold-like equal_weight, momentum_63d, trend_200d | 0, 10, 25 bps |

Stock momentum selects positive 20-session momentum, then equally weights eligible names. It does not rank stocks by momentum strength. SMA selects a short average above the long average. Crypto momentum requires a positive trailing 63-day return; trend requires the previous completed close above its trailing 200-day average. Eligible products receive equal weights; no eligible product means cash. At most 10 stock positions or 20 crypto positions, with gross exposure at most 1, no leverage, no turnover cap and no optimization. Stock pools larger than 10 use the first 10 eligible sorted product identifiers.

## Accounting and interpretation

Each independent fold uses 252 feature-only warmup observations, followed by 63 scored exchange sessions for stocks or 90 calendar days for crypto. Only full, nonoverlapping scoring windows are included. Every fold starts in cash. Signals use the preceding completed close. `lagged_close_proxy` assumes allocation at that preceding close; it is an idealized daily proxy, not a verified executable fill schedule. The first scored entry pays costs and there is no terminal liquidation.

The explicit `self_financing_daily.v1` path marks quantities to prices and charges actual traded notional. It solves post-fee wealth as `E_after = E_before - fee * sum(abs(weight * E_after - current_holding_value))`. This keeps fully invested entry fees cash funded. Legacy paths have different target-weight turnover and fee conventions; their historical output is preserved rather than silently replaced.

Net and zero-fee gross shadows use the same target rules. Return is final normalized wealth minus 1. Cost drag is gross return minus net return. Drawdown is a nonnegative peak-to-trough fraction, including initial wealth 1. Volatility and zero-risk-free Sharpe use sample daily standard deviation and annualization 252 or 365. Zero volatility gives null Sharpe. Costs sum normalized wealth units; turnover sums actual one-way traded notional divided by pretrade wealth. Benchmark excess return is a difference in same-fold, same-cost returns, not alpha. Never compound independent folds into a continuous portfolio.

Mean marked exposure, mean daily one-way turnover and flat-day count are daily-model eligibility proxies. All scoring dates count in the denominator. A flat day requires zero end exposure and no modeled trade. These proxies cannot establish organizer eligibility or capture intraday trading evidence. Current pools introduce selection bias; dividends, tax, financing, discrete lots, capacity, spreads and verified slippage remain unmodeled beyond the stated fee assumptions. Actual account/product authorization remains separate.

## Reproduction

Use an editable checkout for source identity and install the locked offline team profile. Root tools dispatch independent leaf CLIs and consume versioned artifacts. They never import leaf Python. Version 1 evaluation remains unchanged.

```sh
python -m competition_tools.team evaluate --config /external/team.toml --spec /external/study-spec.json --output-root /external/new-study
python -m competition_tools.check_study_delivery --config /external/team.toml --output-root /external/new-synthetic-contract
```

The v2 spec has exactly `schema`, `manifests` and `costs`:

```json
{"schema":"competition.evaluation_spec.v2","manifests":["/external/dataset/manifest.json"],"costs":{"US":[20,40],"HK":[30,60],"crypto":[0,10,25]}}
```

The immutable private plan binds input and source hashes, code commit, jobs, dates, costs and methods before execution. Maximum 384 jobs and 3600 seconds. Each leaf writes `competition.daily_study_result.v1` and private `periods.json`; root verifies identities and hashes. Changed or unavailable inputs are blocked with null metrics. Results remain `accepted_research=false`. Public output is a separate allowlisted projection, never raw period positions or private logs.
