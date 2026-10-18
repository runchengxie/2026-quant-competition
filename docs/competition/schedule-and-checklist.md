# Pre-competition schedule and checklist

> Source: [competition-analysis.md](competition-analysis.md). The organizer's written notices take precedence if dates or rules change.

## Schedule (public organizer rules dated 2026-10-13, checked 2026-10-18)

- Registration deadline: 2026-10-23 23:59 Hong Kong time.
- Final preparation deadline: 2026-10-25 23:59 Hong Kong time.
- Trading period: 2026-10-26 00:00 through 2027-01-27 06:00 Hong Kong time.
- Presentations and awards: expected in February 2027; exact dates have not been announced.

Source: [organizer's public rules page](https://fundconnecthk.com/quant-league/legal/competition-rules/). Check the team registration system and official channels for updates.

## Questions to confirm with the organizer

- [ ] How are minimum share-price limits converted into local currencies for different markets?
- [ ] How is the 30-day average daily turnover threshold calculated?
- [ ] Which market calendars, time zones, currency conversions, and FX sources apply?
- [ ] How are global equity benchmarks selected and cross-market excess returns calculated?
- [ ] Confirm the daily position-rate and turnover numerators, denominators, calendar, and derivative notional. The public rules specify arithmetic daily averages and exclude intraday round trips from flat days.
- [ ] Are weekend NAV, returns, and Sharpe calculations for crypto assets included?
- [ ] Configure all subitems of Trades, Cash Transactions, and Net Asset Value (NAV) Summary in Base in the read-only Activity Flex Query. Keep tokens and Query IDs private and verify account reconciliation.
- [ ] How is the strategy-stability metric defined and over what period?
- [ ] Is the strategy category determined from the application, actual holdings, or primary risk exposure?
[Historical identifying detail removed.]
[Historical identifying detail removed.]
[Historical identifying detail removed.]
[Historical identifying detail removed.]

## Strategy and publication gates

- [ ] Evaluate position/turnover eligibility across the exact competition period, not from closing inventory alone. Missing both routes affects defense/award eligibility, not the ability to continue participating.
- [ ] Treat multiple research candidates as one combined registered strategy only after team selection and account confirmation. Do not split holdings or records across competition accounts.
- [ ] Confirm supported broker, account and product permissions before treating any crypto venue or perpetual contract as eligible.
- [ ] Keep restricted rule copies, registration identities, account records and authorizations outside public Git. Public guidance should cite public official sources.
