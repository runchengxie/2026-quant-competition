# What the returns depend on

The new checks make the limits clearer. US returns are sensitive to a few stocks. The crypto trend rule's advantage is thin and turns negative at the higher tested cost. Neither finding establishes a new out-of-sample edge.

All 114 fixed historical jobs completed, with zero blocked jobs. The same retained replay accounts produced 288 ex-post volume checks. These are separate from the original 420 strategy controls. Every scoring window starts a separate cash account. We do not join the windows into one portfolio return curve.

## US stock exclusions

We kept monthly equal weight, the original eleven 63-session scoring windows, 252-session warmup, and 20/40 bps one-way total fees. The original ten-stock pool remains the control. SPY is also reported gross and net of the same fee, with entry before the scoring window and no terminal liquidation.

| Fixed pool | Fee, bps | Higher-return windows versus original pool | Lower-drawdown windows | Median return change, percentage points | Windows above fee-matched SPY |
| --- | ---: | ---: | ---: | ---: | ---: |
| Without NVDA | 20 | 4/11 | 10/11 | -0.4598 | 8/11 |
| Without NVDA | 40 | 4/11 | 10/11 | -0.4576 | 8/11 |
| Without NVDA, GOOGL, META | 20 | 4/11 | 10/11 | -1.9732 | 4/11 |
| Without NVDA, GOOGL, META | 40 | 4/11 | 10/11 | -1.9687 | 4/11 |
| AAPL, MSFT, JPM, JNJ, XOM, PG | 20 | 4/11 | 10/11 | -2.0482 | 4/11 |
| AAPL, MSFT, JPM, JNJ, XOM, PG | 40 | 4/11 | 10/11 | -2.0428 | 4/11 |

Removing these stocks usually trades some historical return for smaller drawdown. The six-stock subset is a named fixed-current pool, not an authoritative historical sector-balanced universe. The exclusions were motivated by an already inspected sample, so this is a retrospective sensitivity diagnosis rather than an untouched test or a causal estimate of stock contribution. US prices are split-adjusted price returns, not a dividend-inclusive total-return model.

## Crypto total-cost replays

We retained the eight-coin pool, twelve 90-day windows, 252-day warmup, strict trend rule, and matched-target-exposure equal-weight control. Holdings, cash, commissions and net NAV were recomputed at total one-way costs of 35 and 50 bps. These are not extra fees added to those totals, and the results are not a static deduction from the 25 bps path.

| Total fee, bps | Trend has higher return | Trend has lower drawdown | Median return change versus matched control, percentage points |
| --- | ---: | ---: | ---: |
| 35 | 6/12 | 4/12 | +0.1076 |
| 50 | 5/12 | 4/12 | -0.3157 |

Both arms use the same lagged target-gross schedule in each scenario. This does not guarantee equal realized post-fee weights or risk. These medians and win counts are descriptive, not significance tests. The original 0/10/25 bps controls and their published results remain unchanged.

## Ex-post volume checks

For each of the 48 new crypto accounts, we reconstructed asset trade quantities from retained positions and prices and reconciled their value to account turnover. We then compared scaled trade quantities with final daily base-asset volume at three initial USDT notionals and two thresholds. The volume belongs to the lagged-close trade date. It is used after the fact and cannot change strategy decisions.

| Initial notional, USDT | Accounts exceeding 1% | Accounts exceeding 5% | Highest daily participation |
| ---: | ---: | ---: | ---: |
| 10,000 | 0/48 | 0/48 | 0.0597% |
| 100,000 | 0/48 | 0/48 | 0.5968% |
| 1,000,000 | 6/48 | 2/48 | 5.9676% |

No account had missing volume in this retained run. Missing or zero volume is reported as unavailable by the diagnostic, rather than zero participation. These checks are not evidence of available spread, order-book depth, market impact, maker fills or live trading capacity. USDT is not implicitly converted into USD. The 48 related accounts are not 48 independent market samples.

## Reproduction and retained evidence

The fixed grid is 3 US pools × 11 windows × 2 fees = 66 jobs, plus 2 crypto arms × 12 windows × 2 fees = 48 jobs. Each market has a 600-second cumulative run budget including verification; capacity checks share the crypto budget. Reservations bind the original parent and catalog under the owning data root. Changing the output path does not grant another run. Failed or uncertain attempts are not automatically retried.

Root tools invoke independently installed leaf CLIs. They never import leaf or sibling-framework Python. Root verification binds the actual price slices, reconstructs lagged targets, checks every reported period, and solves fee funding with an independent piecewise-linear reference. It also checks SPY's entry boundary and retained holdings without charging a terminal sale.

```powershell
python -m competition_tools.check_strategy_robustness_delivery --config <absolute-team.toml> --output-root <new-external-synthetic-directory>
python -m competition_tools.team robustness --config <absolute-team.toml> --spec <absolute-robustness-spec.json> --output-root <new-external-directory>
```

The first command uses ten explicitly synthetic contract vectors. The second runs the fixed historical grid, requires committed source and exact parent plan/result hashes, and consumes a one-time reservation. Do not rerun it to replace inconvenient results. The spec schema is `competition.strategy_robustness_spec.v1`; versioned plan, job, result, periods and results schemas live under `schemas/research/`.

The scientific run used commit `e70040cc19f4d4f4e826afe295013a348e41b314` and plan `12c04fc53aa450dfb9bbbb66e4978a691e13fef1d36a7b7944ab5720aa7b4291`. The exact reviewed public aggregate is [strategy-robustness.v1.json](../../site/src/data/strategy-robustness.v1.json). It contains all 114 job outcomes, 66 US comparisons, 24 crypto comparisons and 288 volume checks. Raw prices, volume series, receipts, account information and private paths stay outside the public repository.

## Next evidence

Keep the six observation candidates and their original fees. Prepare fresh common warmup data, freeze before the next unseen scored bar, then accept only manually reviewed actual imports. No new market data were downloaded for this stage and no real observations were added. See [data refresh](data-refresh.md) and [the manual registry](observation-registry.md). Synthetic process diagnostics are documented in [operations](../operations/native-process-diagnostics.md).
