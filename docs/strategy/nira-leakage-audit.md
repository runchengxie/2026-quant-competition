# Nira alignment audit

Read-only audit of the current Linux artifact bundle:

- factor artifact: `xgb_daily_optuna.parquet`
- factor rows: 567, from 2024-01-04 through 2026-04-30
- return artifact: `returns_data.parquet`
- return rows: 4,399, from 2008-05-08 through 2026-05-01
- every factor date has a later return date available; the final factor date
  has 2026-05-01 as its next available return date

This confirms that the artifact bundle has enough future dates for a one-day
forward evaluation. It does not, by itself, prove that model features are
leakage-free. The unusually strong historical performance remains blocked
from promotion until feature construction, training-window boundaries,
cross-sectional ranking, and execution-price timing are separately audited.

The reusable date-level check is `strategies.nira.audit.audit_forward_alignment`.
It is intentionally independent of the Linux Nira source tree and can be run
as part of target publication before producing `targets.json`.
