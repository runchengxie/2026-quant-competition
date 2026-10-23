# Bounded data refresh and new observations

The next step is fresh evidence. The historical robustness run downloaded no new market data, and accepted real observations remain zero. Offline preparation produces reviewable request lists and warmup checks. It does not log in, start Gateway, enable scheduling, or approve an import.

## Current prepared requests

The private request plans were frozen on 2026-10-23 UTC. Their completed-date boundary is 2026-10-22. Dates that were still trading or incomplete at preparation time were excluded.

| Market | Retained common date | Prepared range | Planned resources/calls | Activation |
| --- | --- | --- | ---: | --- |
| Crypto | 2026-09-30 | 2026-10-01 through 2026-10-22 UTC | 176 ZIPs + 176 checksums = 352 resources | Not activated |
| US | 2026-10-20 | Five-session overlap from 2026-10-14 through 2026-10-22 | 11 qualifications + 11 historical calls = 22 calls | Not activated |

These dated plans remain private. Their preparation does not reserve provider data availability or promise that requests will complete. Review the exact dates again before activation; a later date requires an explicitly reviewed plan, not silent expansion of the existing request list.

## Crypto daily extension

The source remains Binance Vision spot `1d` candles for the existing BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, ADAUSDT, DOGEUSDT and LINKUSDT pool. Daily archives are a separate identity and parser from the existing monthly archives. According to the [official data documentation](https://github.com/binance/binance-public-data), daily files become available the following day, and spot timestamps from 2025 use microseconds. Earlier files use milliseconds.

The extension spec has exactly four fields:

```json
{
  "schema": "competition.binance_daily_extension.v1",
  "start": "2026-10-01",
  "end": "2026-10-22",
  "parent_sha256": "<sha256-of-the-verified-parent-manifest>"
}
```

The dates must form a contiguous extension after every product's parent tail. A plan contains at most 31 completed UTC dates, 248 ZIPs and 248 checksum resources. The hard limits are 600 attempts including errors, 128 MiB transferred, 256 MiB expanded in total, 4 MiB expanded per ZIP, and 600 cumulative seconds including verification and finalization. Attempt headroom does not authorize additional resources. This implementation makes one attempt per resource and stops on an error or uncertain spend rather than automatically retrying.

Only exact official HTTPS paths are accepted. Redirects, credentials in URLs, wrong checksums, unexpected ZIP members, unsupported products, wrong timestamps, multiple daily bars and invalid OHLCV are rejected. The parent retains its original partial/acquired status. A complete extension slice does not silently turn incomplete older history into a complete parent dataset.

Replace the angle-bracket placeholders with absolute external paths, using the configured roots and installed root interpreter:

```powershell
python -m competition_tools.team daily-extension prepare --config <team.toml> --spec <extension.json> --base-manifest <parent-manifest.json> --output-root <new-plan-directory>
python -m competition_tools.team daily-extension inspect --config <team.toml> --manifest <new-dataset/manifest.json>
```

Both commands are offline. The following command performs real requests and must be used only after approving its exact frozen request list:

```powershell
python -m competition_tools.team daily-extension acquire --config <team.toml> --plan <plan-directory/plan.json> --output-root <new-dataset-directory>
```

A one-time reservation lives under the owning data directory, independently of the output destination. A changed destination, configuration destination or frozen-at timestamp cannot reset it. A failed or uncertain reservation requires explicit investigation and new authorization, not another automatic attempt. Raw ZIPs, checksums, merged normalized files, receipts and manifests remain external. The new `competition.binance_daily_manifest.v1` is inspected through this extension command and observation preparation; it is not automatically accepted by the original historical-study loader.

## US refresh inventory

```powershell
python -m competition_tools.team observation-prepare us-refresh --config <team.toml> --manifest <complete-US-parent-manifest.json> --output-root <new-inventory-directory>
```

This creates `us-refresh-plan.json`, an inventory rather than an executable acquisition spec. It preserves the parent start and identity, selects completed XNYS sessions, and includes the existing five-session overlap. The eleven instruments include SPY. The limits are 22 counted calls, at most 11 historical calls, 10 MiB retained payload including parent data, 300 seconds, and one attempt per request. Pacing alone takes approximately 210 seconds; successful completion is not guaranteed. A revision that needs a larger rebuild must stop for a new bounded plan.

Actual fetching uses the existing explicitly configured daily refresh boundary after activation review. It requires its own v2 acquisition spec and private connection-file reference. Do not pass the new inventory JSON as that spec. Preparation never constructs a broker session. This stage does not activate automatic login or use `--ensure-gateway`.

## Per-market warmup and protocol handoff

```powershell
python -m competition_tools.team observation-prepare market --config <team.toml> --manifest <verified-market-manifest.json> --parent-registry <old-registry-directory> --output-root <new-preparation-directory>
```

The result requires 252 common completed periods, a complete market calendar, an extended warmup and fresh verified data. It records collection time, input hashes, the next eligible market date, unchanged candidates/fees, and zero observations. Stale, gapped or revised inputs stay blocked. Catch-up data are warmup material, not prospective observations.

Once a market has passed these gates, freeze its reviewed preparation explicitly:

```powershell
python -m competition_tools.team observation-prepare freeze-market --config <team.toml> --preparation <preparation.json> --parent-registry <old-registry-directory> --output-root <new-registry-directory>
```

Freezing rechecks freshness and requires committed source. It retains all six candidates and the existing observation v1 fields. To let markets start independently without changing v1, each market may use a separate protocol: the active warmup is replaced, the inactive parent warmup remains, and `relationship.json` records the parent/new protocol IDs, active market and preparation digest externally. The cutoff gate prevents scoring intervening old tails for the inactive market. Track the protocol ID for each market rather than assuming the two starts share one registry.

`known_cutoff` records the inspected price-date boundary; it does not replace actual collection, preparation or freeze timestamps. Freezing adds zero observations and does not grant availability trust. A real import still needs exact manually reviewed evidence registration through the [existing observation registry](observation-registry.md). Do not backdate availability or call an earlier cached tail unseen data.
