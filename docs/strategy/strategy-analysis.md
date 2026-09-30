# Strategy Fit for the 2026 FundConnectHK Quant Competition

## 1. Purpose and status

This document translates and updates historical research written in early September 2026 about the competition fit of non-A-share strategies in the team's GitHub projects. The current schedule follows the organizer's 2026-09-23 public rules. The team has not selected or registered its competition strategy. The Hong Kong equity candidate and the AIVIX-driven U.S. ETF candidate remain under review.

The earlier version favored a long-only/index-enhancement strategy. That was a research recommendation, not a submitted registration decision. Compare the Hong Kong Point-in-Time (PIT) stock candidate and the U.S. ETF candidate on data availability, out-of-sample performance, competition eligibility, and supervised IBKR Paper execution before selecting one.

## 2. Project fit (historical assessment)

| Historical priority | Project / strategy | Market | Potential competition role | Assessment |
|---|---|---|---|---|
| S | Monthly PIT Hong Kong stocks with XGBoost Ranker | Hong Kong | Candidate | Original fit assessment; compare against the new AIVIX candidate. |
| A | `hk-stock-allocation` | Hong Kong | Portfolio implementation evidence | Demonstrates conversion of signals into holdings and orders. |
| A- | CNN walk-forward ranker | Hong Kong | Machine-learning research evidence | Demonstrates deep learning, calibration, and out-of-sample validation. |
| B+ | Global futures | Global futures | Team capability evidence | Systematic modeling and risk allocation, but not a long-only equity-index strategy. |
| B | Intraday trader | U.S. / Hong Kong | Engineering evidence | Backtesting, Paper trading, multiple data and broker adapters, and risk controls. |
| B- | KO/PEP pairs | U.S. | Research reserve | Reconcile hedge ratios and P&L definitions before use. |
| B- | U.S. private-equity sector alpha | U.S. | Research capability evidence | Clarify Point-in-Time, trading constraints, and whether the alpha is external reference material. |
| C+ | Multi-model BTC strategy | Crypto | Technical capability evidence | Its edge depends on OKX spot/perpetual execution, which differs from the IBKR competition setup. |
| Exclude | A/H pairs, CDS basket, and portfolios with A-share ETFs | A-share or mixed | Not recommended for this entry | Does not fit the non-A-share scope or a single consistent strategy category. |

## 3. Hong Kong candidate positioning (historical draft)

Potential descriptive names:

> Hong Kong index-enhancement strategy using Point-in-Time fundamentals and cross-sectional ranking.

> Low-turnover, fundamental-led, machine-learning index enhancement for Hong Kong equities.

Avoid describing the strategy only as an “XGBoost stock-picking strategy” or “deep-learning prediction of Hong Kong stock prices.” That hides the benchmark, active risk, portfolio construction, and trading constraints.

## 4. Candidate strategy logic

### 4.1 Alpha sources

Build PIT historical fundamentals and equity-universe data using information that was available at each historical decision point. This reduces look-ahead caused by restated financials, mismatched publication dates, or later data revisions. Candidate feature families include earnings quality, financial strength, valuation, and other economically interpretable market and fundamental characteristics.

The model ranks stocks relative to one another at each decision time. It does not rely only on predicting the absolute direction of each stock.

### 4.2 Portfolio construction

Model scores should not map mechanically to orders. The portfolio layer should include:

- Top-K holdings and entry/exit buffers.
- Sector concentration and single-name weight limits.
- Liquidity, turnover, and transaction-cost constraints.
- Hong Kong board-lot sizes, cash buffers, and tradability checks.

These rules turn a research signal into an executable index-enhancement portfolio and reduce unnecessary trades caused by small ranking changes near a cutoff.

### 4.3 Validation

Keep signal research, portfolio construction, parameter selection, final out-of-sample evaluation, and execution-cost evaluation separate. Use rolling training, walk-forward evaluation, and a holdout period. Freeze the data version, universe, evaluation period, and configuration. Submission metrics should come from one frozen competition run rather than a mixture of notebooks and data versions.

## 5. Metrics for the Hong Kong index candidate

| Metric | Purpose |
|---|---|
| Annualized excess return / alpha | Measures return above the benchmark. |
| Tracking error | Measures active risk taken to seek excess return. |
| Information ratio | Measures excess return relative to tracking error. |
| Maximum drawdown | Measures absolute portfolio downside. |
| Active drawdown | Measures the worst relative period against the benchmark. |
| Turnover | Helps assess trading feasibility and costs. |
| Monthly hit rate versus benchmark | Shows consistency across months. |
| Sector active exposure | Reveals sector tilts relative to the benchmark. |
| Size, value, and momentum exposure | Identifies hidden style bets. |

The benchmark should match the stock universe. The Hang Seng Index, Hang Seng Composite Index, or another broad Hong Kong equity index may be appropriate depending on coverage, liquidity, and actual tradability. Confirm the choice with the organizer.

## 6. How other projects may support the presentation

### Global futures

Use it as evidence of systematic modeling across assets, risk parity, dynamic risk budgets, and portfolio optimization. Its core is global-futures timing and cross-asset allocation, so it should not be presented as the selected long-only/index-enhancement strategy.

### `hk-stock-allocation`

Use it to explain how research signals can become orders while accounting for Hong Kong board lots, cash buffers, fees, price bands, and holding limits.

### CNN walk-forward ranker

Use it to demonstrate rolling training, purge/embargo methods, probability calibration, cross-sectional ranking, and out-of-sample evaluation. It should support, not replace, the primary strategy explanation.

### Intraday trader

Use it to demonstrate event-driven backtesting, Paper trading, market-data and broker adapters, risk checks, and order execution. Describe the engineering; do not present EMA or Z-score rules alone as the main alpha source.

### KO/PEP pairs

Keep it as market-neutral research until cointegration beta, hedge ratio, dollar neutrality, transaction costs, borrow costs, execution delay, and P&L accounting are consistent.

### U.S. private-equity sector alpha

It can demonstrate PIT data handling, sector neutralization, liquidity filters, transaction-cost analysis, and portfolio evaluation. Clearly distinguish external reference alpha from work developed by the team.

### BTC multi-model strategy

It can demonstrate high-frequency and microstructure machine learning. The original assessment did not prioritize it because its execution depends on OKX spot/perpetual markets. That assessment predates the AIVIX-driven U.S. ETF candidate and should not decide the current entry by itself.

## 7. Historical application-text drafts

The text below records a historical Hong Kong candidate description. It is not approved application language and must not be treated as a selected or registered strategy.

> This is a systematic long-only index-enhancement strategy for the Hong Kong equity market. It follows Point-in-Time principles when constructing historical fundamentals and the investable universe, and combines earnings quality, financial strength, valuation, and other cross-sectional features in a machine-learning ranking model. The portfolio uses Top-K holdings and entry/exit buffers, with limits on sector concentration, individual weights, turnover, liquidity, and transaction costs. Research uses rolling training, walk-forward analysis, and independent out-of-sample evaluation. The objective is to maintain long-term equity exposure while seeking risk-adjusted excess return over a broad Hong Kong equity benchmark.

## 8. Strategy deck

The proposed slide structure is in [strategy-deck-outline.md](strategy-deck-outline.md).

## Sources

- [FundConnectHK official public rules](https://fundconnecthk.com/quant-league/legal/competition-rules/)
- The team's historical research materials and project records.
