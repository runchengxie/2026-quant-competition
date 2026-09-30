# IBKR Candidate Data Probe — 2026-09-03

The probe was read-only: it qualified contracts and requested short historical bars. It never called `placeOrder`.

## Observations

- `1321` with `SMART / TSEJ / JPY` qualified successfully through the Paper Gateway.
- A later three-symbol probe (`1321`, `2800`, `SGOV`) could not complete the normal `ib_insync.connect()` handshake because account/execution requests timed out. This indicates Gateway/session health trouble, not equivalent data permission for those instruments.
- The isolated Python environment needed `tzdata` to parse Japan execution timestamps; it is included in the IBKR optional dependency.

## Decision

Keep the initial international-lite universe small and liquid. Before automated Paper orders, repeat the probe for each candidate and record contract qualification, historical-bar count, latest bar date, currency, exchange, and market-data entitlement. A successful socket connection does not prove that historical or real-time market data is authorized.
