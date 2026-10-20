# Private configuration and data providers

[简体中文](environment-and-providers.zh-CN.md) · [Documentation](../README.md)

Offline demos need none of the credentials below. Read this page when configuring a specific provider or the execution runner.
## Private settings

Use the keys in `.env.example` as a template for a private `.env` stored outside this checkout. The template contains public placeholders only. Use a single `.env` file rather than a separate `.env.local`. The runner reads process environment variables and does not automatically load dotenv files; load the required values into the process environment before starting it. Never commit credentials, account details, order logs, raw provider responses or run artifacts.

## AIVIX / Cryptoracle backup key

Set `CRYPTORACLE_API_KEY` and optionally `CRYPTORACLE_API_KEY_BACKUP` in `.env`, then load them into the process environment. The [Cryptoracle client](../../src/adapters/cryptoracle/client.py) reads both keys and `CRYPTORACLE_API_BASE_URL`:

Use `CRYPTORACLE_API_BASE_URL=https://service.cryptoracle.network/openapi`. The client also adds `/openapi` when an older configuration contains only the official service host; custom URLs keep their configured paths.

```python
from adapters.cryptoracle import CryptoracleClient

client = CryptoracleClient.from_environment(timeout=15.0)
# Read-only token discovery, verified against the service on 2026-10-12.
data = client.post("/v2.1/coin/list", {"timeType": "1h"})
```

Each call tries the primary key first. HTTP 401, 403 or 429, or JSON business code `202` (invalid API key), triggers one attempt with the backup key and the same query. Empty values, example placeholders and duplicate keys are skipped; a backup key can also be used alone. Other HTTP failures, network errors and invalid JSON do not trigger a key change. A non-200 integer JSON business code raises `CryptoracleAPIError`; its `status_code` and `business_code` distinguish HTTP status from provider errors, which can arrive inside HTTP 200 responses. Error messages and settings representations omit credentials and provider error bodies. The client uses HTTPS and rejects redirects rather than forwarding keys to another host.

The client does not automatically load `.env` or select indicator endpoints. The [official API overview](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1) specifies the `/openapi` root, and the [authentication documentation](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1/authentication) specifies the `X-API-KEY` header. The [2026-10-12 validation](cryptoracle-validation-2026-10-12.md) confirms backup-key token discovery through both the configured proxy and direct networking, and invalid-key failover. Indicator/history entitlements and coverage remain unverified.

## Other providers

QuantZone is optional: fill both `QUANTZONE_ACCESS_KEY` and `QUANTZONE_SECRET_KEY` in your local `.env` when access is available. The SDK requires `access_key` and `sign_secret` respectively; a single `QUANTZONE_API_KEY` is insufficient. `QUANTZONE_API_BASE_URL` records the candidate service URL; no QuantZone adapter or authentication flow is implemented yet. These entries do not validate account entitlement or factor coverage.

See the [official QuantZone documentation](https://www.quantzone.tech/docs) for the paired credentials and SDK initialization. Use the service URL shown in your console.

Read-only provider and FX checks are recorded in the [2026-10-02 validation update](provider-fx-validation-2026-10-02.md). The [2026-10-03 ledger delivery](usd-ledger-delivery-2026-10-03.md) is a historical record of the original quant-platform implementation. The competition now owns its accounting implementation, including comparison and next-open experiments, without installing that framework.

The optional [standalone accounting comparison](../research/accounting-comparison.md) ([简体中文](../research/accounting-comparison.zh-CN.md)) retains legacy decisions and compares them with the competition-owned cash/share ledger, on synthetic HK/US inputs, without external framework dependencies. Real daily inputs remain blocked without causal clocks, lots and FX metadata. The existing public snapshot is unchanged.
