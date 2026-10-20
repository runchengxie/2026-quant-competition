# International offline experiments

[简体中文](international-experiments.zh-CN.md)

The competition repository owns two distinct international research experiments. They use explicit external inputs and do not download data, submit orders or establish strategy eligibility. Private configurations, research notes, vendor data and original private Git history are excluded from this delivery.

| Experiment | Installed entry | Environment | Markets |
| --- | --- | --- | --- |
| Six-market monthly fractional-weight diagnostic | `equity_lab.international.six_market_run` | Default `equity-lab`, ordinary libraries | US/HK/UK/AU/CA/SG |
| Frozen schedule next-open price-ledger diagnostic | `platform_compare.next_open.run` | Optional `platform-compare`, local ledger and `exchange-calendars==4.13.2` | US/HK/UK/AU/SG |

Use [team setup](../operations/team-quickstart.md), then copy [the fictional six-market configuration](../../config/examples/international-six-market.synthetic.yaml) outside Git and replace `data_root` with your own absolute external input directory. The template contains an invented allocation and no observations. It does not prove that a dataset is synthetic or licensed.

```sh
python -m competition_tools.team run international --config /absolute/private/team.toml --experiment-config /absolute/private/six-market.yml --output-root /absolute/data/six-market-run-001
```

The installed equity interpreter can also run `python -m equity_lab.international.six_market_run --config FILE --output-dir NEW_EXTERNAL_DIR --json`. All six asset CSVs require `date,close,volume`; five FX CSVs require `date,usd_per_local`. Dates are local daily observations, not intraday availability timestamps. USD is the base currency. The runner requires 24 common calendar months across configured assets and FX. Missing Canada or any other market fails rather than shrinking the experiment. Distribution CSVs, when supplied through `distribution_files`, require `date,cash_per_share,currency,source`.

The original fractional-weight calculation, month-end observation schedule, return components and report schemas are retained. This model is a legacy diagnostic, not a self-financing cash/share ledger or an exchange-session next-open simulator. It aligns existing observations with prior values and rejects some stale daily asset histories; it does not independently validate all missing observations or corporate actions. Its final month-end observation can be reused when no following asset session exists. Distribution coverage is based on the supplied date span, not independently verified payment completeness. Missing/partial distributions make total-return reports unavailable. Daily annualization uses 252 observations, so monthly synthetic fixtures are software tests, not performance evidence. Input hashes detect changed bytes and do not establish vendor provenance. Outputs retain `global_six_market.summary.v1`, `global_six_market.total_return_summary.v1` and `global_six_market.inputs_lock.v1`. Review local reports for private paths before sharing.

## Optional next-open replay

```sh
python -m competition_tools.team setup --config /absolute/private/team.toml --profile framework
python -m competition_tools.team run next-open --config /absolute/private/team.toml --experiment-config /absolute/private/next-open.yml --output-root /absolute/data/next-open-run-001
```

The installed framework interpreter can run `python -m platform_compare.next_open.run --config FILE --output-dir NEW_EXTERNAL_DIR --json`. Configuration is explicit, with `experiment_id`, `strategy_id`, `data_root`, `target_schedule_path`, `signal_cutoff`, `initial_cash_usd`, `sizing_mode`, `max_price_age_days`, `max_fx_age_days`, `production_eligible`, `return_basis` and `reference_cost_bps`. This preserved study uses cutoff `2026-10-01`, fractional sizing, `production_eligible: false`, `return_basis: usd_price_nav` and reference costs `{commission: 5, equity_slippage: 5, fx: 0}`. These are diagnostic protocol restrictions, not a selected trading strategy. No private schedule/default configuration is distributed.

Inputs are a `research.target_schedule.v1` schedule, a hash-bound `dataset-manifest.json` and five ETF files (`US_SPY.csv`, `HK_2800.csv`, `UK_ISF.csv`, `AU_STW.csv`, `SG_ES3.csv`). Five FX files are required (`FX_AUDUSD.csv`, `FX_GBPUSD.csv`, `FX_USDCAD.csv`, `FX_USDHKD.csv`, `FX_USDSGD.csv`); CAD is retained input evidence and does not add a Canadian ETF. Files use `date,open,high,low,close,price_semantics,execution_eligible`. The manifest must declare matching hashes, `execution_eligible: false` and the cutoff. This contract is distinct from the HK/US `competition.accounting_request.v2` adapter.

The signal clock is the latest scheduled UTC close across source sessions. The first following scheduled open must have a source bar, otherwise the run records rejected inputs without using a close-price fallback. Calendars are XNYS/XHKG/XLON/XASX/XSES. Close availability and same-session FX midpoint timing remain explicit assumptions. Results exclude dividends and use USD price NAV. The 36 cost combinations remain diagnostics; zero FX cost is an optimistic lower bound. Input locks use `global_etf_next_open.input_lock.v2` and record the competition implementation in `accounting_engine`. Historical v1 locks remain unchanged.

Both entries refuse existing/source output destinations. Team orchestration keeps child logs under external `<data_root>/2026-quant-competition/team-runs/` and returns only a sanitized result envelope. Neither experiment changes the default five-region rotation, execution contracts or the public historical 24-result snapshot. No new real-data performance claim is published here. Adapters use their scoped MIT license; derived accounting code and tests retain Apache-2.0, attribution and the source inventory.
