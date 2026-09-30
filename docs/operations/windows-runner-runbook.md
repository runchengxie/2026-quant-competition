# Windows Runner Runbook

The Windows machine has four logical processors, 16 GB RAM and no usable GPU.
Run only the light international strategy there, with the default budget of
two workers and 8 GB. Leave the Linux host available for A-share research and
backtests.

Before a supervised Paper run:

1. Start IBKR Gateway Paper on `127.0.0.1:4002`.
2. Confirm `tzdata` is installed for Japan/Hong Kong execution timestamps.
3. Validate `targets.json` and `lineage.json`.
4. Run dry-run first and inspect the event journal.
5. Confirm the kill-switch marker is absent.
6. Use a unique client ID and run lock.
7. After completion, run broker reconciliation and archive evidence.

Live execution remains disabled by default. It requires the explicit live
guards in the runner configuration and human supervision.
