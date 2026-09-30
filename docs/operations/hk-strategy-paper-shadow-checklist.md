# Hong Kong Baseline Strategy: Paper Shadow Checklist

Applies to the low-frequency `momentum_volatility` Hong Kong baseline. Only Paper, dry-run, and read-only validation are currently allowed.

## Data and signals

- [ ] Confirm each daily input is a completed trading-day close; do not treat IBKR delayed Last as a real-time fill price.
- [ ] Confirm the dates, currency, and adjustment/dividend conventions match across the 20 stocks and `2800`.
- [ ] Signal timestamps must precede next-session execution; never use the execution-day close to create a same-day signal.
- [ ] Generate targets only once per month. Put securities with insufficient history or missing contract qualification on an exclusion list.

## Portfolio and competition constraints

- [ ] Default to 10 holdings, no more than 12% per name, and 2% cash.
- [ ] Record position rate, flat days, rebalance turnover, and cost assumptions.
- [ ] Use `2800` to calculate relative return but do not include it in the Hong Kong stock alpha universe.
- [ ] Obtain written confirmation of benchmark, position-rate, turnover, liquidity, and minimum-price definitions.

## IBKR Paper operation

- [ ] Use the Paper IB Gateway at `127.0.0.1:4002` or record the configured TWS Paper port.
- [ ] Qualify each `SEHK/HKD` contract individually; a successful socket connection is not proof of market-data permission.
- [ ] Record real-time market-data errors (for example, 354/10089) separately from delayed data (`marketDataType=3`).
- [ ] Keep `environment=paper` and `dry_run=true`. First validate target generation, order intents, delta planning, and response logging.
- [ ] Keep only one TWS/Gateway API session active at a time to avoid 10197/2103/2110 interference during diagnosis.

## Evidence and release gate

- [ ] For every run, save an input snapshot, resolved configuration, targets, lineage, order intents, responses, and reconciliation results.
- [ ] Run continuous Paper shadow across at least one monthly rebalance cycle and ensure daily reports can be reproduced.
- [ ] Confirm the Flex Query can provide trades, cash transactions, and NAV Summary (Base).
- [ ] Do not enable a live guard or send live orders before all evidence above is available.
