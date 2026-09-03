# IBKR candidate data probe — 2026-09-03

The probe is read-only: it qualifies contracts and requests short historical
bars. It never calls `placeOrder`.

## Observations

- `1321` with `SMART / TSEJ / JPY` qualified successfully in the Paper Gateway.
- A later three-symbol probe (`1321`, `2800`, `SGOV`) could not complete the
  normal `ib_insync.connect()` handshake because account/execution requests
  timed out. This is a Gateway/session health issue, not evidence that the
  three instruments have equivalent data permissions.
- The isolated Python environment needed `tzdata` to parse Japan execution
  timestamps; it is now included in the IBKR optional dependency.

## Decision

Keep the initial international-lite universe small and liquid. Before enabling
automated Paper orders, rerun the probe for each candidate and record contract
qualification, historical-bar count, latest bar date, currency, exchange and
market-data entitlement. Do not treat a successful socket connection as proof
that historical or real-time market data is authorized.
