# Forward-observation readiness

No forward observation has started. The published experiments reuse already inspected historical data and fixed current pools. Their unscored tails are not an untouched test.

Candidates are US weekly `sma_cross`, HK monthly `momentum_20d`, and crypto `trend_200d` risk controls. Candidate status is a research question, not approval, an optimized winner or a claim that every variant improved results. The fixed 60% exposure control remains post-hoc. Review all fees and windows in the [strategy guide](strategies.md#formal-ablation).

Before collecting genuinely new evidence:

1. Freeze fresh immutable data identities and an observation cutoff. Current stocks stop at 2026-10-20 and the selected crypto slice at 2026-09-30.
2. Define the universe and membership dates before observing outcomes. The current ten-stock US/HK pools and eight crypto products are not historical S&P 500 or whole-market membership.
3. Fix corporate-action/dividend assumptions, a tradable execution price, costs, lot sizes and capacity. The present prior-close/close-to-close proxy is insufficient for execution validation.
4. Declare the exact decision calendar, strategy/parameter set, evaluation metrics, stopping conditions and treatment of missing data before new observations. Retain disappointing results and evidence lineage.
5. Separately confirm competition, account, venue and product eligibility. Research artifacts are not executable target handoffs.
6. Authorize any new collector, Paper login, scheduler or order integration separately. None is activated by the retrospective CLI or website.

An eventual report must distinguish protocol freeze time from data availability and actual execution time. It must retain independent cash starts unless a separately versioned continuous-account protocol is implemented. Current publication contains aggregate window comparisons only and does not start a live performance track record.
