# USD portfolio accounting integration design

Date: 2026-10-02
Status: design approved by the user on 2026-10-02; implementation plan awaiting review

## Intent

Move the international competition research baseline from native-currency fixed-weight return diagnostics to reproducible USD portfolio accounting. Retain the ETF/equity/futures research direction, while delivering an independently valid cash-equity/ETF ledger first. Futures require a separate settlement/margin capability and must fail closed until supported. This design does not enable v2 broker execution.

## Evidence and ownership

- Five regional equity ETF historical series and five explicitly qualified IBKR FX series are locally available. Canadian XIU history remains unavailable.
- Index One authenticated FX queries work, but the queried values are too coarsely represented to adopt for high-precision HKD valuation. Equity/ETF adjusted-price coverage is not verified.
- AIVIX documented token-list endpoints returned 404. Provider-specific endpoint confirmation is pending; no crypto signal is available yet.
- Competition `AGENTS.md` assigns research/backtest/raw-data ownership outside the execution repository.
- `quant-platform/AGENTS.md` assigns reusable backtest/accounting mechanisms to quant-platform, data acquisition to quant-market-data-platform, and strategy hypotheses/parameters to the private research layer. No provider, credential or real dataset may be added to quant-platform.
- Existing platform helpers include `portfolio_backtester.execution_ledger`, `trade_accounting` and backend trade accounting. Their single-currency, shared-lot and/or A-share settlement assumptions require explicit adaptation. `quant_execution_engine.fx` reads static environment/config rates; it is not a historical as-of FX series engine. Never use it to backfill historical valuations.

## Approaches considered

1. Extend the competition fixed-weight loop with converted prices. This preserves its implicit constant-weight daily return calculation and cannot establish monthly buy-and-hold accounting.
2. Reuse the public platform's ledger interfaces and add a generic historical currency-aware accounting capability there; competition/research supplies strategy targets and immutable datasets through published interfaces. **Recommended**, because it follows ownership and records shares, cash and costs explicitly.
3. Run the whole research experiment through Index One simulation. Actual asset coverage, adjusted-price definitions, workflow state and source precision remain unverified; this is a later independent comparison, not the accounting foundation.

## Deliverables and boundaries

### Stage A — USD price-NAV ledger

Build a deterministic generic mechanism in quant-platform; do not import it via an absolute checkout path. Pin a published package or reachable reviewed commit when the research/runtime consumes it. Competition-side integration remains a thin artifact consumer.

Inputs are caller-supplied instrument metadata, price observations, FX observations, a target schedule and an explicit research clock. No hardcoded provider clients, competition symbols, strategy parameters or live accounts enter the mechanism. Required observation metadata identifies source, base/quote currency, unit/scale, bar time, availability time, and immutable data version. Fractional shares are an explicit research mode; venue lot validation and broker submission are later execution capabilities.

The first supported assets are long-only cash equities and ETFs. Cash remains in USD, with assumed zero interest. Explicit modeled spot conversion on each local-currency buy/sell avoids pretending to maintain local cash balances. FX spread/cost assumptions must be supplied and recorded separately from equity commission/slippage. Futures, shorts, leverage, taxes, margin and foreign-currency cash ledgers are rejected until separately supported.

Stage A outputs are explicitly **USD price-NAV research diagnostics**. Missing dividend/corporate-action capability must not silently produce a total-return label or promotion-ready performance claim.

### Stage B — cash flows and corporate actions

Add only after a trusted source defines splits, dividend ex/pay dates, cash currency, reinvestment policy, revisions and availability timestamps. Splits change shares and marks consistently; cash dividends enter cash according to the selected explicit entitlement/payment convention. Do not combine adjusted prices and dividend cash flows. A provider's `adjClose` label alone is insufficient to establish its adjustment convention. The total-return capability remains unavailable until covered by ledger reconciliation tests.

## Accounting rules

1. Maintain quantities `q_i` and USD cash. At valuation time, `NAV = cash_USD + sum(q_i * local_mark_i * USD_per_local_i)`.
2. Between trades, quantities remain fixed. Prices/FX change position values and weights naturally. Initial/all-cash periods stay in NAV and performance output.
3. Target schedules specify decision time and earliest execution time. A signal cannot consume a closing mark and fill at that same close. Fill and valuation marks must respect the source's availability clock. When only historical bar dates exist, an explicitly declared conservative lag is permitted solely for diagnostics; it cannot be represented as verified PIT metadata or an executable fill.
4. On rebalance, value existing inventory first, then execute permitted sells and buys with cost-adjusted USD cash. Deduct transaction/FX costs once from actual traded notional; never manufacture cash or silently borrow. Order/sizing must be deterministic. After eligible sells and their costs, cap unaffordable fractional buy increments proportionally to available USD cash including buy/FX costs; integral mode rounds each increment down to its explicit lot. Record requested versus executed quantities, residual cash and scaling. Other affordability policies require an explicit versioned extension.
5. A full liquidation/empty target schedule is supported by the research ledger. It must not be forced through the nonempty execution-target v2 contract. Lot rounding, residual cash and rejected orders are recorded if integral sizing is selected.
6. FX direction is explicit. Reject unknown units, invalid/nonpositive prices/rates, duplicate identity/times, unmatched column lengths, and unavailable currencies. No implicit parity conversion, backward fill from future data, averaging sources or cross-source replacement is allowed.
7. Use bounded backward as-of matching for valuation only, with a supplied maximum age. Stale/missing inputs prevent a successful valuation. Trading requires eligible executable marks and session policy; a carried historical close is not a trade price.
8. NAV changes reconcile to local-price P&L, FX P&L and costs; no unexplained residual is accepted. USD conversion and fixed quantities must not change local-return signal definitions silently. Preserve the existing baseline signal schedule as a separately versioned input; changing signals is another experiment.

## Clocks, calendars and reporting

Use an explicit UTC valuation grid and per-market availability/session policy. A shared calendar-date intersection alone is not a supported synchronization rule. For current date-only input, disclose assumed availability and conservative lag; retain the raw date and source semantics. Historical data must have a specified cutoff before strategy generation.

Report cumulative NAV return and drawdown over all valuation observations. Calendar-time CAGR uses actual elapsed time. Sharpe requires an explicit sampling/annualization policy; do not assume 252 observations for an irregular cross-market intersection. Benchmark uses the same valuations, cash/cost convention and data capability.

Publish immutable data hashes, source/unit metadata, configuration digest, research clock, quantity/cash ledger and diagnostics through existing research result contracts. A competition target handoff is a separate artifact, with no account information or silent v2-to-v1 conversion. Unsupported futures must fail before publication of a successful result.

## Validation and acceptance

- USD asset with flat prices and no trades keeps NAV constant; nonzero cash is retained.
- Local price flat with changing FX gives exactly the expected USD P&L; direct/inverse FX representations agree.
- Two assets with divergent prices retain quantities between monthly trades and exhibit weight drift; no cost-free implicit daily rebalance.
- Rebalance/initial buys/liquidation charge costs once, reconcile cash, and cannot overspend or create negative cash in long-only mode.
- Empty/all-cash schedules, fractional versus integral sizing and residual cash are explicitly covered.
- Future-available marks, stale rates, unmatched columns, invalid units and unsupported futures fail closed.
- Corporate-action tests prevent adjusted-price/dividend double counting before Stage B is enabled.
- Real-data evidence is private and reproducible; synthetic fixtures and generic tests are public. No licensed/raw provider data or credentials are committed.
- Each repository uses isolated worktrees, local tests, independent review and its own PR. Merge/delete only the current task's resources.

## Out of scope

Selecting the final competition strategy, introducing broker execution, claiming total returns from the current price histories, automatic futures rolling, provider entitlement changes, live trading or publishing current positions.

## Required review before implementation

Review this accounting and repository-ownership design first. After approval, write a separate implementation plan identifying existing platform interfaces, exact input/output types, synthetic reconciliation tests and the thin research/competition consumer boundary. No accounting implementation is authorized by this draft alone.
