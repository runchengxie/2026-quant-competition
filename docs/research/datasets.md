# Standalone research datasets

[简体中文](datasets.zh-CN.md)

The competition repository owns these offline preparation tools. They require no quant-series checkout. Root orchestration uses the standard library. Daily crypto evaluation stays in the existing crypto environment; execution packages do not import it.

## Commands and storage

Install the locked offline profile using [team quickstart](../operations/team-quickstart.md). Keep `competition.team.v1` unchanged. Create a separate external JSON dataset specification, then run:

```sh
python -m competition_tools.team data plan --config /absolute/private/team.toml --spec /absolute/private/dataset.json
python -m competition_tools.team data acquire --config /absolute/private/team.toml --spec /absolute/private/dataset.json
python -m competition_tools.team data inspect --config /absolute/private/team.toml --spec /absolute/private/dataset.json --manifest /absolute/data/2026-quant-competition/datasets/spot-study/v1/manifest.json
```

`plan` and `inspect` make no network requests. By default, `acquire` does not start Gateway or log in. Only explicit IBKR acquisition may use the optional [Paper login precondition](../operations/gateway-login.md#optional-data-task-login-precondition) with `--ensure-gateway` and an activated private deployment. The separate Databento pilot below supports an explicitly authorized metered download. No dataset mode submits orders. The result uses the existing `competition.team_result.v1` envelope. Legacy partial coverage returns exit2 with `PARTIAL_COVERAGE`; it is not a completed acquisition.

Data lives below configured `DATA_ROOT/2026-quant-competition/datasets/<dataset-id>/<version>/`. For the legacy v1/v2 sources, successful publication is exclusive and partial runs remain in `<version>.partial` with a manifest, receipt, request ledger and per-file checkpoints. Repeating the identical specification verifies completed hashes and resumes missing downloads. A different specification cannot reuse that staging directory. Existing published versions are never overwritten. A revised upstream archive requires a new version and new acquisition. Resume verifies retained bytes, not whether the upstream publisher has since revised them. The Databento pilot uses the separate single-attempt behavior below.

## Databento daily ingestion pilot

This pilot prepares data for inspection; it does not produce new strategy returns. The separate `competition.databento_dataset_spec.v1` contract fixes `EQUS.SUMMARY`, `ohlcv-1d`, USD raw prices and the UTC interval `[2025-01-01, 2026-01-01)`. Its fixed pool is SPY, QQQ, IWM, TLT, GLD, AAPL, MSFT, NVDA, AMZN and META. This is a current fixed pool, not historical S&P 500 membership.

Keep `databento.env` outside Git with one literal `DATABENTO_API_KEY=...` assignment. Create the external specification using the installed root environment:

```python
import json
from pathlib import Path
from competition_tools.datasets.databento_spec import pilot_spec

credential = Path("/absolute/private/providers/databento.env")
specification = Path("/absolute/private/databento-pilot.json")
with specification.open("x", encoding="utf-8") as stream:
    json.dump(pilot_spec(credential), stream, indent=2)
```

On Windows, use absolute drive paths. Run `team data plan`, `acquire` and `inspect` with the same flags shown above and the new specification. `plan` requires no key or network. Calendar inspection uses the optional locked `daily-data` profile. `refresh`, parent manifests and Gateway options are rejected for this namespace. Review the plan and authorize the metered request before invoking `acquire`.

The cap is USD 0.10, five metadata calls, one download attempt, 120 seconds total active time and 20 MiB of uncompressed HTTP response bytes. All attempts and failed-response bytes count. A fresh quote, billable-size/count checks and applicable unit pricing must support a conservative cost bound before downloading. The server request has a 4,000-record limit; a reached limit or inconsistent count rejects the result. Billing is based on uncompressed binary data, not the CSV file size. An unavailable cost proof produces a blocked receipt rather than an assumed zero cost. See the [official HTTP API](https://databento.com/docs/api-reference-historical?historical=http).

Outputs remain under `databento-us-daily-pilot/20261023-v1/`, including blocked or partial attempts. The parent `.databento-us-2025-pilot.attempt` marker reserves this pilot authorization before preflight, and `download-attempt.json` records that a billable request may have started. Neither failed requests nor interrupted downloads retry automatically. Do not remove those markers or select another directory to repeat an uncertain request; reconcile retained evidence and account usage first. Repeating acquisition is rejected, while offline `inspect` verifies file hashes and request/spec identity.

Raw CSV, dated instrument mappings, normalized per-symbol CSV, coverage, calendar provenance and a `competition.databento_dataset_manifest.v1` receipt are retained externally. Unknown listing-calendar evidence is reported as `LISTING_CALENDAR_UNVERIFIED`; missing observations are never filled. `raw` prices remain unadjusted and corporate actions remain unverified. Every result has `accepted_research=false`. Existing accepted-study inputs still require their original provider and adjustment contracts.

The [final Summary daily bar](https://databento.com/docs/datasets/equs-summary) includes post-market volume and is published at approximately 20:15 America/New_York. Its midnight bar timestamp is not its availability time. The receipt distinguishes this publication assumption from observed acquisition time and does not certify historical availability. A future strategy integration must resolve adjustments and execute only after its inputs were available.

CoinPaprika Business remains a separate candidate: local connection checks failed before receiving an API response. This does not establish an invalid key or a verified plan. No CoinPaprika acquisition adapter is delivered here.

An acquisition lock prevents two CLI runs from modifying the same version. After a crash, inspect the owning process and retained checkpoint before manually removing a stale lock. The tools do not break locks automatically or update shared `current`/`latest` pointers.

## Binance spot daily archives

This is an explicitly selected additional source, never a fallback for the four previously configured providers. The following external specification requests a disclosed fixed study pool:

```json
{
  "schema": "competition.dataset_spec.v1",
  "dataset_id": "spot-study",
  "version": "v1",
  "source": "binance_spot",
  "market": "crypto",
  "products": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LINKUSDT"],
  "quote_currency": "USDT",
  "start": "2023-01-01",
  "end": "2025-12-31",
  "timezone": "UTC",
  "calendar": "365",
  "price_basis": "raw",
  "universe_status": "fixed_current",
  "budget": {"requests": 5000, "bytes": 1073741824, "seconds": 3600}
}
```

Only completed monthly `1d` spot archives are acquired. Products must use the common USDT quote, with at most 20 products. Each ZIP is checked against its matching `.CHECKSUM`, then its one expected CSV is validated. Unsafe paths, symlinks, unexpected members, files over 25 MiB compressed or 100 MiB expanded, nonfinite values, invalid OHLCV, duplicate dates and incorrect month/day timestamps are rejected. Spot timestamps use milliseconds before 2025 and microseconds from 2025, following the [publisher's format](https://github.com/binance/binance-public-data).

The pilot budget is 20 requests, 25MiB and 600 seconds. The expanded cap is 5000 requests, 1 GiB and 3600 seconds. The current downloader is sequential. All network attempts count, including retries and404 responses. Each resource allows at most 3 attempts and 30 seconds per request; Retry-After is capped at 60 seconds and the total wall-time budget still applies. Host/path allowlists and redirect rejection prevent implicit source changes. Incomplete months, unavailable archives and stopped runs remain explicit gaps. Daily candles cannot supply order-book depth or market-maker fills. USDT is not USD.

## Equity inputs and S&P500 limits

`licensed_import` accepts an explicit external `input_directory` containing `<product>.csv` files with exactly `date,open,high,low,close,volume`. Specify market, currency, calendar, timezone and raw/adjusted basis. The importer records source hashes and validates bars; it does not establish vendor entitlement, adjustment correctness or publication timing.

For `point_in_time`, also provide an external `membership_file` with `stable_id,symbol,valid_from,valid_to,available_at`. Intervals must not overlap for the same identity. Empty or unrelated intervals are rejected, as are intervals with unknown availability. Each requested product needs relevant membership evidence within the requested range. `membership.eligible` uses both effective intervals and information available by the stated cutoff. Importing intervals does not automatically apply a historical selection rule to an existing engine. Licensed crypto daily imports can be marked acquired only when the continuous 365-day requested range is complete. Exchange-calendar imports remain partial with `CALENDAR_COVERAGE_UNVERIFIED`: the importer has no authoritative exchange-session schedule and does not demand weekend or holiday bars. Changed retained source or membership bytes require a new version.

A current list must remain `fixed_current`. Neither SPY nor a current constituent list is a historical S&P500 stock-selection universe. Full expansion needs licensed historical membership, stable identities, delistings/corporate-action evidence and compatible price history. No removed members are fabricated.

`ibkr` offers an explicit one-month Paper historical-data pilot only. Use the optional `broker-data` profile, an external `credential_file` containing only `host`, `port`, `client_id`, and an explicit contract list with `product`, `con_id`, `exchange`, `currency`. Only loopback Paper port 4002 is accepted. Use `price_basis=split_adjusted`: [IBKR documents](https://www.interactivebrokers.com/docs/tws-api/doc/md/historical-bars) `TRADES` bars as split-adjusted, not dividend-adjusted. It connects read-only, requests daily RTH `TRADES`, disconnects, and retains empty/partial outcomes. It does not run a multi-year or full-universe broker download. A successful pilot is not complete requested coverage. Use the separate v2 mode below for a bounded fixed pool; historical index membership remains unverified.

Algoseek, AIVIX, Index One and CoinPaprika currently expose readiness blockers in this subsystem, not guessed authenticated download endpoints. `PROVIDER_CONTRACT_UNVERIFIED` does not mean their service has no such product. Existing provider integrations elsewhere remain unchanged. Missing access never causes a paid request or silent source substitution.

## Contracts and evidence

The JSON schemas under `schemas/research/` define `competition.dataset_spec.v1`, `competition.dataset_manifest.v1`, `competition.dataset_receipt.v1` and `competition.coverage_report.v1`. Manifests bind source/specification, requested range, observed coverage, unknown availability, raw/normalized hashes, sizes, row counts, revisions/checksums and normalization lineage. Publication timing remains unknown unless independently evidenced. New datasets do not satisfy the existing `accepted_research` gate or replace event input receipts.

Full receipts and raw observations stay external. Pages receives only the allowlisted aggregate from [the evaluation report](data-expansion-and-evaluation.md). New dataset/evaluation modules are MIT licensed in their directories; this does not relicense unrelated execution code or upstream datasets.

## Bounded daily equity snapshots

Use `setup --profile daily-data` to install the optional locked broker and exchange-calendar dependencies. Default offline delivery stays unchanged. `competition.dataset_spec.v2` uses `source=ibkr_daily`, an external `connection_file`, explicit stock contracts and a separate benchmark. It supports US/USD/XNYS/`America/New_York` and HK/HKD/XHKG/`Asia/Hong_Kong`. This is a fixed current pool, not historical index membership. [US](../../config/examples/us-fixed-daily.json) and [HK](../../config/examples/hk-fixed-daily.json) examples contain a placeholder: copy them outside source, replace `connection_file` with an absolute external endpoint JSON, choose a new version and set the range before running.

```powershell
& $pythonPath -m competition_tools.team data plan --config $teamConfig --spec $dailySpec
& $pythonPath -m competition_tools.team data acquire --config $teamConfig --spec $dailySpec
& $pythonPath -m competition_tools.team data inspect --config $teamConfig --spec $dailySpec --manifest $dailyManifest
& $pythonPath -m competition_tools.team data refresh --config $teamConfig --spec $nextVersionSpec --base-manifest $dailyManifest
```

The mode accepts at most 20 stocks plus one benchmark. Symbol, exchange and currency must match qualified broker stock contracts. A guarded single-Paper-prefix session precedes requests. Calendar schedules include holidays, half-days and DST; only sessions closed at acquisition time count. Bars are daily RTH split-adjusted TRADES, not dividend-adjusted total returns. No forward fill is applied. All requested stocks and the benchmark must cover all completed sessions to receive `acquired`; source/corporate-action quality and research acceptance remain unverified.

Per-market caps are 120 application broker requests, 32 MiB retained raw/normalized payload and 2400 seconds. Qualification and failed calls count, requests are sequential with at least ten seconds between starts, and collection stops on a broker error without retry or login. Annual-or-shorter windows use explicit end times. These are application budgets, not broker entitlement promises or wire-byte measurements. Raw files contain parsed SDK daily bars; normalized files use `date,open,high,low,close,volume`.

Completed snapshots have immutable `competition.dataset_manifest.v2` and `competition.dataset_receipt.v2` evidence, including file hashes, resolved identities, calendar version/schedule hash, budgets and gaps. `inspect` returns `competition.coverage_report.v2`. Partial attempts stay under owned `.partial` staging with `receipt.json` and verified checkpoints, without publishing an immutable manifest. Repeating the same acquire can resume within its remaining cumulative budget. Changed specs, payload corruption or a changed completed-session grid require manual inspection or a new version. Stale locks are never deleted automatically.

Refresh requires a complete verified parent, a new version, unchanged dataset/product/start/price identities and a nondecreasing end date. It copies parent payloads into new staging, checks the last five available completed sessions and records the parent manifest hash without a private path. Changed overlap triggers full affected-instrument rebuilding; a budget-short rebuild remains partial. An unchanged overlap cannot rule out revisions farther back. `last_full_verification` is retained conservatively for refreshes, and corporate actions/out-of-overlap revisions remain `not_verified`. Parent payloads are never modified and no latest pointer is updated. The v1 `ibkr` pilot and opt-in startup semantics remain unchanged; v2 collection does not start Gateway or authorize orders.

A provider may return a zero-volume, flat-OHLC placeholder on a calendar-closed date. Such bars remain in raw payloads, are excluded from normalized trading sessions and appear in `excluded_non_session_bars` with reason `CLOSED_SESSION_ZERO_VOLUME_FLAT`. Non-session bars with volume or a price range still block collection. This was observed on 2023-07-17, when [HKEX cancelled all trading sessions](https://www.hkex.com.hk/News/Market-Communications/2023/2307172news?sc_lang=en). Exclusion does not fill missing sessions or verify corporate actions.
