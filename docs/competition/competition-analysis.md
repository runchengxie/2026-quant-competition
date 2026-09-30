# 2026 Hong Kong Quant Competition: Analysis and Strategy Notes

> Originally drafted on 2026-08-26 from the rules then available. The schedule below follows the organizer's public rules dated 2026-09-23. This is research material, not investment, legal, or compliance advice. No strategy has been selected or registered.

## 1. Competition overview

The competition combines a short trading stage with a presentation. The trading score uses net return (25%), Sharpe ratio (35%), maximum drawdown (25%), and strategy stability (15%); the final score weights trading at 70% and the presentation at 30%. The competition may identify teams for later asset-management cooperation, but participation or an award does not guarantee a capital allocation.

Current dates, in Hong Kong time:

- Registration deadline: 2026-10-23 23:59.
- Trading: 2026-10-26 00:00 through 2027-01-27 06:00.
- Presentations and awards are expected in February 2027; the organizer has not published an exact date.

See the [official public rules page](https://fundconnecthk.com/quant-league/legal/competition-rules/) and [pre-competition checklist](schedule-and-checklist.md).

## 2. Strategy choice and eligibility

Potential categories include market-neutral/relative-value, systematic directional, long-only/index enhancement, and hybrid/other. The team's current candidates are:

- Hong Kong Point-in-Time fundamental and cross-sectional stock ranking.
- A U.S. ETF portfolio driven in part by AIVIX crypto sentiment signals.

Both require data-entitlement checks, out-of-sample validation, transaction-cost analysis, and Paper execution before a selection. Only one strategy may be registered for the team account. AIVIX award eligibility requires application through the team portal, actual use of the data, and a clear explanation of its contribution.

To qualify for awards, a strategy must maintain either an average daily position rate of at least 50% with no more than 10 cumulative flat trading days, or average daily turnover of at least 100%. The official rules do not fully specify all calculation details; confirm them with the organizer.

## 3. Accounts and data security

The competition uses IBKR accounts. The organizer states that teams should not provide their IBKR login password. Competition data collection uses read-only Flex access; the scope of fields and setup must be confirmed in the team portal. Keep API credentials, account identifiers, order records, and raw provider data out of public documents and source control.

Potentially sensitive Flex fields can include cash activity, NAV and daily valuation, holdings and market values, cash movements, trades, fees, financing, and account identifiers. Use a minimum-necessary field set and store tokens locally.

## 4. Organizer and partner claims

The rules name Fund Connect HK as organizer and the University of Hong Kong Web3 Institute as co-organizer. Do not describe the event as hosted by the University of Hong Kong unless an official university source supports that wording. Public company-name history is not sufficient evidence of ownership, university sponsorship, or a formal commercial relationship; verify those claims against corporate records and official announcements before using them externally.

The rules describe potential asset-management cooperation opportunities of approximately HKD 100 million equivalent in aggregate. This is not a cash prize or a guaranteed allocation. Any future arrangement would require continued performance review, risk assessment, due diligence, compliance approval, and a signed agreement.

## 5. Research implications

The trading window is roughly three months, which may provide few observations for low-frequency strategies. In addition to long-horizon annualized measures, evaluate the exact competition window, monthly path, drawdowns, turnover, and stability. Freeze the competition run's data version, universe, model, portfolio rules, costs, and evaluation period so that submitted results come from one reproducible source.

For the Hong Kong equity candidate, choose a benchmark that matches the actual tradable universe, such as the Hang Seng Index or Hang Seng Composite Index, subject to final universe coverage and organizer confirmation. Useful diagnostics include annualized excess return, tracking error, information ratio, maximum and active drawdown, turnover, monthly benchmark hit rate, sector active exposure, and size/value/momentum exposures.

For the U.S. ETF candidate, validate the availability and publication timestamps of AIVIX observations, survivorship-safe ETF data, market calendar alignment, FX and transaction costs, and how the strategy maintains competition eligibility. Index One calculations should use the same frozen portfolio-weight manifest that feeds the execution target file, followed by an independent weight reconciliation.

## 6. Supporting project work

- The Hong Kong execution pipeline demonstrates how targets can be validated and translated into Paper order intents with a cash buffer, lot-size handling, liquidity checks, and audit records.
- The machine-learning research materials demonstrate Point-in-Time data handling, walk-forward validation, calibration, and out-of-sample evaluation. They do not establish competition performance by themselves.
- The global-futures, ETF-rotation, intraday, pairs, and crypto projects can illustrate engineering or research capabilities, but should not be presented as the competition's selected strategy unless formally selected and supported by evidence.
- External strategy or reference alpha must be clearly distinguished from work developed by the team.

## 7. Questions for the organizer

Confirm benchmark selection, holding-rate and turnover formulas, derivative exposure conventions, stock-price and liquidity rules across currencies, weekend crypto valuation, market calendars, FX conversion, and stability scoring. Also confirm account permissions and the minimum Flex fields needed for scoring. Keep the written responses with the internal competition record.

## Sources

- [Official competition rules](https://fundconnecthk.com/quant-league/legal/competition-rules/)
- [Competition overview](https://fundconnecthk.com/quant-league/)
