# Integration readiness — 2026-10-02

This update supplements the earlier [local readiness check](local-readiness-2026-10-02.md). Provider responses, licensed raw data, account details and performance artifacts remain local and ignored.

## Verified

### QuantZone

- Paired Access Key and Secret Key authenticated successfully using official SDK 0.10.0 and the console service URL.
- Read-only `get_quota()` and `list_factors()` requests succeeded. A transient catalog network error was resolved by one retry.
- The returned catalog exposes factor name and start/end dates. It does not supply formula/version, point-in-time availability, revision history or redistribution evidence needed by our factor contract.
- No factor observations were downloaded or incorporated into a strategy. No QuantZone dependency or adapter was added to the execution package; the SDK was used in an isolated local environment.
- Our configuration names map `QUANTZONE_ACCESS_KEY` to SDK `access_key` and `QUANTZONE_SECRET_KEY` to SDK `sign_secret`. A single legacy `QUANTZONE_API_KEY` is not sufficient. See the [official documentation](https://www.quantzone.tech/docs).

### IBKR historical data

- A read-only API session completed on the configured Paper port, beyond the earlier TCP-only probe. No order method was called. Port configuration alone is not independent proof of account mode.
- SPY and 2800 contracts qualified and returned short daily historical samples.
- Subsequent requests obtained approximately three years of daily TRADES bars for SPY, 2800, ISF, STW and ES3 after contract qualification.
- XIU contract qualification succeeded but historical bars were unavailable; the local log reported a market-data permission error. Canadian history must be resolved before claiming the original six-market baseline is complete.
- The data does not establish real-time entitlement, execution permissions or a complete order lifecycle.

### Research baseline and target handoff

- The existing rotation implementation ran on the five available regional equity ETF series, using a static selected universe and an intersection of calendar dates.
- Invalid/nonfinite prices, duplicate dates and negative/nonfinite volumes were checked. Bars later than the local-date cutoff were excluded, including an Australian bar beyond that cutoff.
- Effective post-warmup sample: 2024-12-02 to 2026-09-30, 423 common-date observations. Momentum and defended variants use prior-date signals and monthly rebalancing.
- This is a native-currency price proxy, not an investable USD NAV: FX conversion, dividends, total-return accounting, venue-session alignment and independent out-of-sample selection remain unverified. The legacy Sharpe calculation assumes 252 annual observations despite the smaller common calendar; treat it as a diagnostic proxy.
- No AIVIX, Index One or QuantZone observations were used. This is an ETF equity research subset, not the requested complete ETF/equity/futures portfolio.
- A research v2 manifest with three targets parsed successfully. The current execution runner rejected it as designed without journal creation or broker submission. No holdings or strategy parameters are published here.

### Contract integration

- [Target manifest v2](../strategy/target-manifest-v2.md) was merged through PR #21.
- Main verification: 277 tests passed, Ruff and compileall passed. The installed IBKR dependency emitted one event-loop deprecation warning; it did not fail verification.
- Independent review found no Critical, Important or Minor defects. The v1 reader/schema remain unchanged and both runner methods reject v2 before execution effects.
- Feature branch/worktree cleanup completed; unrelated branches were retained.

## Next work

1. Resolve Canadian history permissions or explicitly approve a revised research universe.
2. Add FX and corporate-action/total-return accounting, with regional availability timestamps and reproducible lineage.
3. Validate AIVIX and Index One responses and actual index coverage; provider configuration alone is not an integration test.
4. Assess QuantZone factor formula/version, PIT timestamps, revisions, universe and research/publication rights before consuming observations.
5. Design capital/FX sizing, multi-market contract qualification and risk controls before enabling v2 Paper execution; validate account mode and supervise order acknowledgment, cancellation, fills, reconnection and reconciliation.
