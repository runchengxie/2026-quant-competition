# Strategy guide

These strategies are fixed daily research comparisons, not approved execution strategies. Read the [study methods](real-data-study.md) and [dataset contract](datasets.md) before interpreting results. The homepage links each strategy to this guide and compares only a common market, fee and scored window.

## Shared assumptions and evidence

The frozen 2026-10-21 study contains 318 completed strategy/window/cost jobs. Stocks use 63 scored trading periods per window, crypto uses 90 daily periods, each after 252 warmup periods. Windows restart from cash independently. Input pools are fixed current selections, not point-in-time historical index membership. The US pool has ten instruments, HK ten and crypto eight. Dataset identity, coverage, adjustment and selection limitations are documented in the study, not inferred from a strategy name.

Signals use the prior close and holdings earn the next close-to-close move. The model is long-only and cash-funded. Initial entry incurs costs; final holdings are not liquidated. Stock periods annualize at 252 and crypto at 365. Dividends, taxes, financing, discrete lots, capacity and independently verified execution slippage are not modeled beyond the declared fees. No strategy here connects to a broker or establishes competition eligibility.

The fixed one-way cost assumptions are US 20/40 bps, HK 30/60 bps and crypto 0/10/25 bps. Zero cost is a control. The homepage defaults to nonzero 20/30/10 bps. Use the fee summary to compare the same windows at every declared fee, including the zero-cost control. Missing benchmark values are excluded from the positive-excess denominator; zero excess is not a win. These are descriptive statistics, not significance tests or new out-of-sample evidence.

<a id="buy-hold"></a>
## Buy and hold: `buy_hold`

Stock research initially allocates equally across up to ten instruments in sorted identifier order, then lets weights drift with prices. It does not rebalance back to equal weights daily. Its main risks are market declines, concentration from drifting weights and a selected current pool. A positive window return alone does not establish benchmark outperformance.

Implementation: [stock study](../../research/equity-lab/src/equity_lab/study/run.py). Compare with `equal_weight` under the same market, window and fee to inspect rebalancing effects.

<a id="equal-weight"></a>
## Equal weight: `equal_weight`

For stocks, each daily decision equally weights up to ten sorted instruments. For crypto, the fixed spot pool is initially equal-weighted and then held with drifting weights. The same identifier therefore describes different allocation rules across these separate experiments. Crypto `equal_weight` is also the declared benchmark, so its excess against itself is zero.

Stock rebalancing can add turnover and cost drag. Neither implementation protects against broad market declines. Compare only within the same market. Implementations: [stocks](../../research/equity-lab/src/equity_lab/study/run.py) and [crypto daily study](../../research/crypto-mm/src/crypto_mm/daily/study.py).

<a id="momentum-20d"></a>
## Positive momentum over 20 sessions: `momentum_20d`

The stock model selects instruments whose prior-close return over 20 sessions is strictly positive. It takes up to ten qualifying instruments in sorted identifier order and weights them equally, or holds cash when none qualify. This is a sign filter, not cross-sectional momentum ranking. Targets can change daily.

Near-zero signals can switch repeatedly and increase costs. The filter can lag sudden reversals and miss rebounds after a decline. Inspect turnover, fee sensitivity and the worst window alongside median return. Sources: [signal](../../research/equity-lab/src/equity_lab/signals/momentum.py) and [allocation](../../research/equity-lab/src/equity_lab/study/run.py).

<a id="sma-cross"></a>
## Moving-average filter: `sma_cross`

At the prior close, the stock model selects instruments whose 20-session average is strictly above their 60-session average. It takes up to ten in sorted identifier order, equally weights them and holds cash when none qualify. This is a daily state filter, not an intraday crossover fill model.

Sideways prices can cause repeated position changes, while delayed signals can miss the start of a rebound. Compare against hold and equal-weight baselines at both declared stock fees. Sources: [signal](../../research/equity-lab/src/equity_lab/signals/sma.py) and [allocation](../../research/equity-lab/src/equity_lab/study/run.py).

<a id="benchmark-buy-hold"></a>
## Stock benchmark: `benchmark_buy_hold`

This holds the predeclared single-instrument stock reference. It is a comparison baseline, not a recommended portfolio. Its window returns remain public, but daily normalized benchmark curves are deliberately withheld because they are price-linked. The comparison table can therefore show a benchmark result without adding a benchmark line.

The benchmark does not recreate the selected stock pool, and its own benchmark excess is zero. Consult [study evidence](real-data-study.md) for the benchmark and pool definitions.

<a id="momentum-63d"></a>
## Positive crypto momentum over 63 daily periods: `momentum_63d`

The daily spot model equally weights assets whose prior close exceeds their close 63 daily periods earlier, and holds cash if none qualify. This is positive trailing return selection, not ranking, shorting or a derivative strategy.

Frequent changes near the threshold can incur costs. Volatility and sharp reversals can dominate results. Inspect the same-window comparison and the matched-window fee summary. Implementation: [crypto daily study](../../research/crypto-mm/src/crypto_mm/daily/study.py).

<a id="trend-200d"></a>
## Crypto 200-period trend filter: `trend_200d`

The daily spot model equally weights assets whose prior close is strictly above their trailing 200-period average, or holds cash if none qualify. It does not scale positions by volatility or use a turnover buffer. Those are possible future experiments, not delivered features.

The filter can lag reversals and repeatedly enter or exit near the moving average. Lower exposure does not guarantee a smaller drawdown. Inspect worst windows and higher-fee outcomes rather than selecting one favorable curve. Implementation: [crypto daily study](../../research/crypto-mm/src/crypto_mm/daily/study.py).

## Reproduce and inspect

First follow the [team quickstart](../operations/team-quickstart.md) for an editable checkout and the locked offline profile. Real-data replay needs authorized immutable dataset manifests, the external team configuration and a v2 study specification. The root command runs the fixed matrix of strategies supported by each manifest; it has no single-strategy flag. A new source commit or different inputs produce a new research identity, not an exact reconstruction of the original artifact hashes.

```sh
python -m competition_tools.team evaluate --help
python -m competition_tools.team evaluate --config /external/team.toml --spec /external/study-spec.json --output-root /external/new-study
python -m competition_tools.evaluation.study_publication --aggregate /external/new-study/run/study-results.json --output /external/new-public-study.json
```

Keep these paths outside the source checkout and use new output paths. The public repository does not distribute the licensed raw inputs. Use the separate synthetic delivery check to exercise the CLI contracts without claiming real-data performance:

```sh
python -m competition_tools.check_study_delivery --config /external/team.toml --output-root /external/new-synthetic-contract
```

[Open the performance dashboard](https://runchengxie.github.io/2026-quant-competition/#performance). Compare strategies at the same fee and exact window. Use fee robustness across matching windows to inspect cost dependence. Independent windows are never compounded into a continuous account, and this presentation update does not rerun or promote any strategy.
