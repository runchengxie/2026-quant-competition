# International Portfolio Research and Paper Execution Design

Date: 2026-10-01

## Goal

Build a reproducible first-round research program covering international ETFs, individual equities, and futures. Compare the three asset sleeves independently, then test whether evidence supports combining them into one competition strategy. The competition team will still register one strategy in one official account.

The first round is broad in instrument type. It does not assume that every market, product, data history, or provider permission is already available.

## User decisions

- The research direction is an international portfolio rather than an A-share strategy.
- Initial candidate coverage includes ETFs, individual equities, and futures.
- AIVIX, Index One, and IBKR are intended to participate in the research and validation workflow.
- Use IBKR Paper for supervised execution validation. Live trading is outside this design.
- Research and checks should run locally while the GitHub Actions quota is unavailable. CI must never receive provider or broker credentials.

## Constraints and evidence

- The competition rules permit products supported by the participating broker and the account's actual permissions. A team registers one strategy and one official competition account; multiple components must be presented as one combined or hybrid strategy.
- The competition's award eligibility requires either average daily holding of at least 50% with no more than 10 flat trading days, or average daily turnover of at least 100%. Instrument eligibility and calculation details must be verified with the organizer before registration.
- AIVIX's special award requires applying through the team portal, actually using the data in the competition strategy, and explaining its contribution; API availability alone does not qualify.
- Stocks below USD 1 or with trailing 30-day average daily turnover below USD 3 million are generally restricted to closing positions. Futures must not be used in a way that manufactures abnormal returns through illiquidity.
- Cryptoracle documents net sentiment (`CO-A-02-03`), standardized sentiment momentum (`CO-S-01-01`), and cross-platform sentiment divergence (`CO-A-02-07/08`). These are candidate research inputs for digital-asset-related exposure, not assumed predictors for unrelated stocks, bonds, or futures.
- The current public Index One operation catalog exposes securities reference data, stock EOD data, FX data, and index operations. It does not currently advertise an operation specifically for futures. The actual team API permissions, market coverage, and history depth remain to be confirmed.
- QuantZone publicly describes factor queries, a precomputed factor library, a trading calendar, and a Python SDK, with a free tier described as providing basic daily quota. Its public landing page does not establish the exact market coverage, point-in-time history/revision semantics, or rights to publish derived outputs; those must be verified through account documentation and terms before use. [QuantZone](https://www.quantzone.tech/), [QuantZone SDK on PyPI](https://pypi.org/project/quantzone/).
- The target handoff is version 1.0 and describes symbols, weights, optional quantities, and a market. Its market schema currently lists `JP` and `US`; the internal market model also contains `HK`. It has no futures contract month, multiplier, tick size, or roll metadata. Futures cannot safely use the current target contract unchanged.

Official sources: [competition rules](https://fundconnecthk.com/quant-league/legal/competition-rules/), [Cryptoracle indicator catalog](https://cryptoracle.gitbook.io/cryptoracle-docs/co-indicator-repository), [Cryptoracle CO-S-01-01](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1/api-list/co-real-time-data/indicators/co-s-01-01), and [Index One operation catalog](https://indexone.io/docs/reference/execution-engine).

## Recommended architecture

Use one research framework with three isolated asset sleeves and a common evaluation boundary. Keep instrument-specific data and accounting rules inside each sleeve; normalize outputs only at the portfolio comparison boundary. This preserves breadth without pretending that stock shares and futures contracts have the same sizing, calendars, or costs.

```text
Provider snapshots
  ├─ IBKR prices, contract metadata, and account permissions
  ├─ Index One supported securities, FX, and index/backtest operations
  ├─ QuantZone candidate A-share factor values/metadata (only after entitlement and PIT validation)
  └─ AIVIX / Cryptoracle timestamped indicators for digital-asset exposure
          ↓
Point-in-time instrument and data manifest
  ├─ ETF sleeve
  ├─ Individual-equity sleeve
  └─ Futures sleeve with explicit contract and roll rules
          ↓
Common evaluation: costs, currency conversion, risk, and walk-forward tests
          ↓
Candidate portfolio comparison → one frozen target manifest + lineage
          ├─ Index One reconciliation where the instrument universe is supported
          └─ versioned execution handoff → IBKR Paper preflight and supervised tests
```

### Instrument and data boundary

Every instrument record must identify asset class, canonical symbol, exchange or venue, trading currency, exchange calendar, provider identifiers, valid dates, and the source of each field. Equity and ETF records also need corporate-action handling. Futures records additionally need the expiry/contract month, multiplier, tick size, margin treatment, settlement convention, and a deterministic roll rule. Do not infer a continuous futures history from a current front-month symbol.

Each observation carries its provider timestamp, retrieval timestamp, period boundaries, currency, and source/version identifier. The research cutoff is explicit for each market session. Historical decisions may use only observations available by that cutoff. Corrections or late provider data are retained as later versions; they do not silently rewrite a frozen run.

### Provider responsibilities

- **IBKR:** qualify actual contracts, verify account permissions, and provide Paper execution events. Market-data entitlements must be checked separately from TCP/API connectivity. Paper is the only execution environment in this design.
- **Index One:** first use the live public schema and team permissions to inventory the exact supported operations. Use its prices, FX, index values, weights, or backtest functions only for verified supported instruments. Reconcile results against the same frozen target manifest used by execution. Do not assume its securities EOD operations cover futures. Use documented backtest-only endpoints for experiments; avoid arbitrary workflow execution or persistent index writes until the exact operation and permission are confirmed.
- **AIVIX / Cryptoracle:** begin with a small, predeclared BTC/ETH sentiment set. Store the indicator ID, asset, provider period, publish/observation time, retrieval time, and response checksum. Test net sentiment, standardized sentiment momentum, and cross-platform divergence separately. A stale, missing, revised, or malformed input disables the AIVIX overlay for that decision and selects the documented baseline allocation; it does not invent a value or stop unrelated sleeves.
- **QuantZone:** evaluate as a candidate A-share factor source, not as an assumed global data provider. Before use, verify eligible A-share markets/universes, factor definitions and versions, adjustment and survivorship treatment, historical depth, first-available/as-of timestamps, revisions, rate limits, price/terms, and permission to use factors in research and publish sanitized derived results. Preserve factor ID, formula/version, instrument identity, observation period, availability timestamp, retrieval timestamp, and source snapshot. For other markets, use its catalog only to generate hypotheses; reconstruct factors from region-appropriate data and refit/validate them independently. Do not transplant A-share ranks, thresholds, or factor values across markets without evidence.

Provider keys stay in local environment configuration. They must not enter Git, GitHub workflow logs, Pages, run artifacts, or public test fixtures. Do not request or publish raw licensed provider responses.

### Research sleeves and combined portfolio

- **ETF sleeve:** compare broad regional equity, fixed-income, commodity, and other liquid listed ETF candidates supported by available data and the Paper account. Track fund domicile, currency, benchmark, expense effects where data is available, and trading calendar.
- **Individual-equity sleeve:** use a point-in-time eligible universe, historical membership and delisting treatment where available, corporate actions, liquidity and price screens, and market-specific calendars. If survivorship-safe history is unavailable, label the result as a limited proxy and do not treat it as proof of historical performance.
- **Futures sleeve:** test only contracts with verified historical data and IBKR contract metadata. Model multiplier, margin, expiry, roll timing, roll cost, session calendar, and currency explicitly. Keep risk sizing in exposure/risk units as well as contract counts.
- **Combined portfolio:** initially compare sleeve outputs using common reporting currency, portfolio NAV, risk budget, and timestamped rebalance dates. Do not combine sleeves into a competition candidate until each sleeve has a valid cost model and the combined portfolio passes exposure, drawdown, leverage/margin, liquidity, and contest eligibility checks.

The AIVIX experiment compares a no-AIVIX baseline, a price-only risk overlay, and the same digital-asset sleeve with AIVIX data. Other sleeves remain unchanged in this experiment so any incremental effect can be attributed to the signal. The final combined allocation may use AIVIX only if it adds out-of-sample value after costs and does not jeopardize required holdings or risk limits.

### Evaluation and output contracts

Use matched decision dates where possible and explicitly report any sleeve that has shorter history or different session timing. Convert results to a declared reporting currency with point-in-time FX. Apply instrument-specific commissions, spread/slippage, market impact assumptions, taxes or exchange fees where applicable, ETF/fund effects where material, and futures roll and financing costs.

Each run freezes the universe, data snapshot identifiers, decision cutoffs, strategy parameters, cost model, evaluation period, and software version. Report net return, risk-adjusted return, maximum drawdown, turnover, exposure, tracking error or benchmark-relative measures where meaningful, signal coverage, and missing-data days. Use walk-forward validation and a held-out period. No result is presented as established alpha or Paper execution until its evidence supports that claim.

The execution handoff must be versioned to describe security and futures instruments safely. Keep version 1.0 readers working during migration. A futures target must not be reduced to a ticker and weight without the contract month, multiplier, currency, and roll/expiry identity required to reconstruct the intended exposure. Index One output is reconciled to the exact same dated manifest, not used as an independent order source.

## Failure and safety behavior

- Missing or stale data blocks the affected signal and records why; the system uses an explicit fallback only where the approved portfolio rules define one.
- Unverified instrument permissions, unresolved contract identifiers, missing futures roll metadata, or non-reconciling weights block target publication or Paper submission.
- A failed Index One request does not become fabricated history or weights. If Index One cannot represent a futures sleeve, that sleeve remains independently evaluated and is not silently included in Index One totals.
- Paper order tests require a confirmed Paper account, qualified contracts, preflight, position reconciliation, a kill-switch check, and supervised limits. No live order path is added by this work.
- Public Pages show project method and reviewed, sanitized findings only. They do not show credentials, raw provider responses, account identifiers, holdings, orders, or unverified returns.

## Validation gates

1. Inventory supported markets, asset classes, historical depth, timestamps, licensing, and rate limits for AIVIX, Index One, and IBKR without exposing keys.
2. Confirm futures trading and data permissions in the Paper account and confirm with the organizer how futures, ETFs, cash, and the 50% holding/100% turnover tests are counted. If pursuing the AIVIX award, confirm the team-portal application is recorded and document how the signal affects the submitted strategy.
3. Freeze a point-in-time data sample and instrument manifest for each sleeve; test exchange calendars, currencies, corporate actions, missing observations, and futures rolls.
4. Reproduce each sleeve's backtest from its frozen inputs with costs and a held-out evaluation period. Compare the three AIVIX variants on matching dates.
5. Compare combined candidates and reject portfolios that fail broker, liquidity, drawdown, leverage/margin, contest eligibility, or data-quality gates.
6. Version the target/lineage handoff and validate round-trip compatibility before enabling any Paper order submission.
7. Complete supervised Paper qualification, submit/cancel/fill event handling, restart recovery, and reconciliation checks before calling the execution workflow operational.
8. Select and register one strategy only after the comparison and organizer/account checks. Record the final strategy category, assets, benchmark, data use, and risk controls consistently in registration material and the public project description.

## Out of scope

- Live-money orders, unattended trading, or changes to production account permissions.
- Treating AIVIX sentiment as a universal signal for global equities, bonds, or unrelated futures.
- Assuming Index One supports every exchange, ETF, equity, futures contract, or historical field before validating the live operation catalog and team entitlements.
- Adding the QuantZone SDK or making authenticated API calls before confirming account access, actual A-share coverage, point-in-time/revision semantics, quotas, pricing, and use/publication terms.
- Using A-share QuantZone factor values directly for non-A-share markets; only factor hypotheses may transfer before market-specific reconstruction and validation.
- Publishing raw market data, credentials, account information, or unverified performance.
