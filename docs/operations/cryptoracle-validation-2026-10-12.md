# Cryptoracle backup-key validation — 2026-10-12

The configured backup key authenticated successfully for read-only token discovery. Both the configured local HTTP proxy and explicit direct networking returned HTTP 200 with JSON business code `200` and `msg=success` for:

```text
POST https://service.cryptoracle.network/openapi/v2.1/coin/list
Content-Type: application/json
X-API-KEY: <loaded privately from local configuration>
{"timeType": "1h"}
```

The [official API overview](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1) identifies the `/openapi` API root. Combine that prefix with the versioned path from the [token-list documentation](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1/api-list/co-private-data/token-list). Earlier requests omitted `/openapi`; both network routes returned nginx HTML 404 responses for the incomplete URL.

Authentication comparisons on the corrected path returned HTTP 200 with business code `201` for a missing header and `202` (`APIKEY invalid`) for a synthetic invalid key. Consequently, HTTP success alone does not establish API success. The client retries with the backup on business code `202`, in addition to HTTP 401/403/429, and reports other non-200 integer business codes as errors.

The corrected client's invalid-primary-key to real-backup-key retry was verified with a synthetic primary credential. Credentials and raw provider data were not printed, saved or committed. This verifies token discovery and authentication only; indicator values, history entitlement, completeness and signal suitability remain unverified. No broker connection or order was attempted.
