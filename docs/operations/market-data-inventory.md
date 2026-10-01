# Market and Asset Data Inventory

> Snapshot date: 2026-09-10. This public summary omits local absolute paths, account identifiers, credentials, and raw provider files. It describes the team's research data snapshot, not a guarantee of current vendor entitlements. A file's presence, a configuration entry, and a permission probe are different evidence types.

## Summary

| Status | Market / asset | Snapshot coverage | Frequency / level | Notes |
|---|---|---|---|---|
| Stored | Hong Kong equities | 20 liquid stocks, 2023-09-05 to 2026-09-03 | Daily OHLCV, IBKR `TRADES` bars | Price proxy for research; not historical index membership or PIT fundamentals. |
| Stored | Hong Kong ETF | 2800, 2023-09-05 to 2026-09-03 | Daily close and volume | Global multi-market research proxy, not the competition's stock universe. |
| Stored | Multi-market ETFs | SPY, 2800, ISF, STW, XIU, ES3; through 2026-09-03/04 | Daily close and volume | Cross-market allocation research, not the competition strategy. These are price-return diagnostics, not total-return series. |
| Stored | FX | USDHKD, GBPUSD, AUDUSD, USDCAD, USDSGD; through 2026-09-04 | Daily | Used for USD conversion diagnostics in multi-market research; verify aliases against the input manifest. |
| Stored | Equity-index futures | U.S., Europe, Japan, and Hong Kong contracts; mostly through 2026-08-05, some international contracts through 2026-07-17 | Continuous-contract 1-minute OHLCV | Databento GLBX/international continuous-contract research. Not order-book data. |
| Stored | Energy, metals, agriculture, and rates futures | Selected U.S. contracts; through 2026-08-05 | Continuous-contract 1-minute OHLCV | One micro Bitcoin futures contract is included; it is not spot crypto or exchange order-book data. |
| Stored | U.S. Treasury ETF | TLT through 2026-02-09 | 1-minute OHLCV | Stored with futures research but must be treated as ETF data. |
| Stored | Vietnam equities | 50-stock pilot through 2026-08-27 | Daily data from VCI and KBS, raw and normalized | Quality report is `PASS_WITH_QUARANTINE`; adjustment semantics remain unresolved and `factor_ready=false`. |
| Probe only | Selected U.S., Hong Kong, Japan, Singapore, U.K., Australia, Canada, and Germany securities | Short history/contract checks around 2026-09-03/04 | Permission or contract probe | Not complete research datasets. Some exchanges returned no historical-data permission. |
| Candidate / not yet validated | QuantZone factor library | No factor snapshots validated in this repository | Factor query service and Python SDK are publicly described; account entitlement and project-specific market coverage have not been checked | Do not treat advertised stock/factor counts or a free basic quota as proof of A-share coverage, point-in-time history, or publication rights. |

## Hong Kong competition data

The snapshot includes 20 liquid Hong Kong stocks with 738 daily bars per symbol from 2023-09-05 through 2026-09-03. Fields include date, OHLC, volume, average, and bar count. The data came from IBKR historical `TRADES` bars using daily regular-session requests. The files had no duplicate dates or missing closes in the checked snapshot.

This is a price proxy for currently liquid securities. It is not a survivorship-safe historical universe, historical Stock Connect membership, or PIT fundamental dataset. The 2800 series has only daily close and volume and is kept separate from the stock alpha universe.

No complete Hong Kong ETF universe, historical Hang Seng Composite constituents, or competition-grade PIT dataset was present in the audited snapshot.

## Multi-market ETFs and FX

The ETF snapshot contains SPY (U.S.), 2800 (Hong Kong), ISF (U.K.), STW (Australia), XIU (Canada), and ES3 (Singapore), with roughly 738–760 daily records each. The experiments label these as price-return research diagnostics. They are not total-return data and do not include a complete FX-hedged investable portfolio accounting model.

Five daily FX series are available: USDHKD, GBPUSD, AUDUSD, USDCAD, and USDSGD. Common history runs approximately from 2023-09-06 to 2026-09-04. The multi-market project remains exploratory; it has not completed Paper shadow validation or established competition eligibility.

## Futures and derivatives

The research snapshot has continuous-contract one-minute OHLCV for selected equity-index, energy, metal, agricultural, interest-rate, and micro Bitcoin futures, plus TLT ETF bars. Event timestamps are UTC and records include trading day, continuous-contract symbol, and volume. Monthly volume rules stitch the continuous series, so it is not one fixed expiry contract. The data is neither tick/order-level nor five- or ten-level order-book data. Use each coverage manifest for the exact date range; the broadest common end date is not shared by every instrument.

## Vietnam equities

The research pilot contains 50 equities across HOSE, HNX, and UPCoM. Its listing master has 3,586 records, including delisted and unknown-exchange entries; that does not mean 3,586 names have complete prices. Daily price data has 175,554 rows from 2018-01-02 to 2026-08-27, sourced from VCI and KBS with raw, normalized, and adjudicated records. The quality state is `PASS_WITH_QUARANTINE` with 454 quarantined rows. Corporate-action and adjustment semantics are unresolved, so the data is not factor-ready. It is daily OHLCV/listing/corporate-action diagnostic data, not real-time, tick, or order-book data.

## Permission-probe limitations

Historical contract probes help establish that a contract can be identified or that a short historical request returned. They do not establish a complete dataset or current real-time entitlement. In the 2026-09 probe snapshot, Hong Kong examples had historical and delayed data but no confirmed real-time subscription; some Japan and Germany contracts returned no historical-data permission. FX and futures real-time permissions were not stably confirmed. Gateway connectivity errors must be distinguished from market-data subscription errors.

## Missing or unconnected data

- Complete historical PIT fundamentals and index membership for the Hong Kong competition universe.
- Confirmed real-time Hong Kong quotes, Level 1 bid/ask, depth, ticks, or order-book data.
- A resident real-time monitoring service for the competition strategy.
- Complete history for most securities used only in permission probes.
- Vietnam real-time, depth, and tick data.
- Futures tick, MBO, and order-book data in the described one-minute dataset.
- QuantZone factor definitions and observations with verified A-share universe, formula/version, point-in-time availability and revision history, survivorship/adjustment treatment, quota/price, and research/publication rights.

## Usage notes

1. Treat the Hong Kong baseline as a 20-stock daily-price proxy with PIT fundamentals missing; keep 2800 and global ETF data outside its stock universe.
2. For real-time monitoring, separately record quote status, bid/ask, timestamps, permissions, reconnect count, and Gateway session identifier.
3. Distinguish data snapshots and duplicate copies by their manifests and coverage files.
4. Do not use Vietnam prices as production factors until adjustment semantics are resolved.
5. External data directories are not version-controlled. Use manifests, input locks, and file hashes to establish provenance.
6. QuantZone is a candidate A-share factor source only. Before using it, verify the factor formula/version, supported market/universe, point-in-time availability timestamp, revisions, corporate-action and survivorship treatment, quotas/pricing, and rights for research and sanitized publication. For other markets, factor names may inspire hypotheses; reconstruct from regional native data and validate separately. Do not copy A-share values, ranks, or cutoffs to other markets.

Public product references: [QuantZone](https://www.quantzone.tech/) and [QuantZone Python SDK on PyPI](https://pypi.org/project/quantzone/). These describe the product and SDK, not this team's entitlements or data-quality validation.
