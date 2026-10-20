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

`plan` and `inspect` make no network requests. By default, `acquire` does not start Gateway or log in. Only explicit IBKR acquisition may use the optional [Paper login precondition](../operations/gateway-login.md#optional-data-task-login-precondition) with `--ensure-gateway` and an activated private deployment. No mode purchases data or submits orders. The result uses the existing `competition.team_result.v1` envelope. Partial coverage returns exit2 with `PARTIAL_COVERAGE`; it is not a completed acquisition.

Data lives below configured `DATA_ROOT/2026-quant-competition/datasets/<dataset-id>/<version>/`. Successful publication is exclusive. Partial runs remain in `<version>.partial` with a manifest, receipt, request ledger and per-file checkpoints. Repeating the identical specification verifies completed hashes and resumes missing downloads. A different specification cannot reuse that staging directory. Existing published versions are never overwritten. A revised upstream archive requires a new version and new acquisition. Resume verifies retained bytes, not whether the upstream publisher has since revised them.

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

`ibkr` offers an explicit one-month Paper historical-data pilot only. Use the optional `broker-data` profile, an external `credential_file` containing only `host`, `port`, `client_id`, and an explicit contract list with `product`, `con_id`, `exchange`, `currency`. Only loopback Paper port 4002 is accepted. Use `price_basis=split_adjusted`: [IBKR documents](https://www.interactivebrokers.com/docs/tws-api/doc/md/historical-bars) `TRADES` bars as split-adjusted, not dividend-adjusted. It connects read-only, requests daily RTH `TRADES`, disconnects, and retains empty/partial outcomes. It does not run a multi-year or full-universe broker download. A successful pilot is not complete requested coverage. Bulk broker expansion remains deferred until actual readiness and membership/price prerequisites are met.

Algoseek, AIVIX, Index One and CoinPaprika currently expose readiness blockers in this subsystem, not guessed authenticated download endpoints. `PROVIDER_CONTRACT_UNVERIFIED` does not mean their service has no such product. Existing provider integrations elsewhere remain unchanged. Missing access never causes a paid request or silent source substitution.

## Contracts and evidence

The JSON schemas under `schemas/research/` define `competition.dataset_spec.v1`, `competition.dataset_manifest.v1`, `competition.dataset_receipt.v1` and `competition.coverage_report.v1`. Manifests bind source/specification, requested range, observed coverage, unknown availability, raw/normalized hashes, sizes, row counts, revisions/checksums and normalization lineage. Publication timing remains unknown unless independently evidenced. New datasets do not satisfy the existing `accepted_research` gate or replace event input receipts.

Full receipts and raw observations stay external. Pages receives only the allowlisted aggregate from [the evaluation report](data-expansion-and-evaluation.md). New dataset/evaluation modules are MIT licensed in their directories; this does not relicense unrelated execution code or upstream datasets.
