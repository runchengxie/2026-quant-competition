# Provider and FX validation — 2026-10-02

All queries in this update were read-only. Credentials and raw responses remain in ignored local directories; no index workflow was persisted and no broker order was sent.

## Index One

The public `/schema` catalog and OpenAPI specification were retrieved successfully. A team-key-authenticated `/execute` request ran only the `i1_core_fx` dataset operation with explicit date and identifier filters; it did not contain storage, deployment or delivery operations.

The FX operation completed without an operation error. The live response is keyed by operation ID, and its output is column-oriented (`id`, `date`, `close`); it differs from the array-oriented documentation example. A successful HTTP status alone is insufficient: validate operation state, output shape, matching column lengths and requested filters.

A single-date query returned currency pairs, and a subsequent bounded historical query returned the project's five candidate USD pairs for 2023-10-03 through 2026-10-01. The selected histories had no missing/nonpositive closes or duplicate dates. This verifies this FX query only, not equity/index constituent coverage or portfolio eligibility.

The returned candidate FX values had at most two decimal places; HKDUSD had one unique close across the queried history. Cross-source checks found a materially larger HKDUSD discrepancy than the other project pairs. Do not treat the queried Index One FX output as a high-precision valuation source. Preserve it separately for source diagnostics, and ask the provider whether a more precise series or interface is available.

Official references: [operation catalog](https://api.indexone.io/schema), [OpenAPI specification](https://indexone.io/openapi.json), [execution-engine documentation](https://indexone.io/docs/reference/execution-engine).

## Cryptoracle / AIVIX

The configured host matches the [official authentication documentation](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1/authentication.md). A small supported-token query used the documented `X-API-KEY` header and JSON request body.

Both the current documented `/v2.1/coin/list` and the earlier documented `/v2/coin/list` returned HTTP 404 with non-JSON responses. Authentication and indicator access therefore remain unverified. A 404 does not establish that the key is invalid; confirm the competition team's supported endpoint/version or private service URL before additional requests.

No indicator observations were downloaded. No crypto risk overlay was applied to the equity ETF baseline.

## IBKR FX

Five explicit Forex contracts qualified and returned historical daily MIDPOINT bars: USDHKD, GBPUSD, AUDUSD, USDCAD and USDSGD. Each series contains 776 rows, spanning 2023-10-04 through 2026-10-01. Keep MIDPOINT marks separate from trade prices, and do not infer executable spreads or FX conversion fees from these bars.

The contract's base symbol and quote currency were checked. For USD per unit of local currency, GBPUSD/AUDUSD are direct; USDHKD/USDCAD/USDSGD require explicit inversion. A matching calendar date does not prove simultaneous source timestamps. Source differences need retained diagnostics rather than automatic averaging or substitution.

## Local data locations

Relative to the competition checkout:

- `runs/global-etf-real-2026-10-02/`: five ETF CSV histories, research baseline and v2 target artifacts.
- `runs/fx-historical-2026-10-02/`: five IBKR FX CSV histories and collection summary.
- `runs/provider-discovery-2026-10-02/`: public documentation snapshots, private Index One FX responses and quality/cross-source summaries.
- `runs/quantzone-probe-2026-10-02/`: private quota and catalog results; no factor observations.

These are local validation artifacts, not a released dataset. Production acquisition and versioned data assets belong to the market-data platform; the research platform consumes immutable published inputs. No data relocation or provider data publication occurred in this update.

## Accounting gap

The current competition baseline applies fixed target weights to each daily return and charges turnover on monthly target changes. It does not carry share quantities and residual cash between dates. Its earlier returns remain a diagnostic proxy: FX conversion alone will not establish a self-financing monthly portfolio.

The proposed [USD accounting design](../superpowers/specs/2026-10-02-usd-portfolio-accounting-design.md) replaces this proxy for future research evidence, with a quantity/cash ledger, causal marks, source-unit checks and explicit price-only versus total-return capabilities.
