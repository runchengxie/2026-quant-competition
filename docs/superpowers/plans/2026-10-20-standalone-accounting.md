# Standalone Accounting Implementation Plan

**Goal:** Remove framework dependencies from optional competition experiments.

**Architecture:** Preserve the existing CLI adapters and vendor only their
required accounting dependency closure into a competition-owned namespace.

**Tech stack:** Python 3.12, pandas, NumPy, PyArrow, exchange-calendars, pytest, uv.

**Spec:** ../specs/2026-10-20-standalone-accounting-design.md

## Global constraints

Keep all environments, baseline artifacts and test outputs under the configured
external competition data root. Preserve historical artifacts and existing user
work. Retain the upstream Apache-2.0 license separately from MIT adapters.

## Review focus

- No eager imports of framework packages through package initializers.
- Both HK/US comparison and five-market next-open paths remain runnable.
- New engine identity cannot falsely attest to historical provider artifacts.
- Wheel installation includes the accounting closure and license files.
- Bundle tampering, future prices and missing bars still fail closed.

## Tasks

1. Capture baseline optional tests and eight-case accounting outputs. Add and run
   failing isolation tests that block framework imports and inspect wheel metadata.
2. Vendor the pinned accounting closure and relevant ledger tests with provenance;
   switch adapters, dependency declarations and locks to the local implementation.
   Preserve monetary results and explicit historical ancestry.
3. Update root identity checks, schemas where needed, CI and bilingual guides.
   Keep framework profile as a compatibility alias. Ignore rebuildable build/.
4. Run full suites, baseline comparison and installed-wheel isolation checks;
   review the complete branch, resolve findings, create PR, wait for applicable
   checks, merge and verify target/deployment, then clean only this task's resources.

## Progress

- Inspection: root build/ is entirely reproducible; unrelated docs PR #42 retained.
- Implementation follows the migration scope the user approved in conversation.

- RED: original optional suite 55 passed; three new isolation checks failed on actual
  framework metadata/imports. Expanded root lock/import boundary checks also failed.
- GREEN: 173 standalone tests, 562 root tests, five outside-source installed-wheel
  checks passed. Exact parity: eight cases/64 tables and 36 next-open scenarios/288
  tables; all diagnostics equal and cost-sensitivity CSV bytes identical.
- Independent review found no Critical/Important issues. Clarified both languages'
  license boundary and recorded schema-namespace changes in provenance metadata.
- Root build/ removed after rechecking all 86 source hashes and rejecting reparse
  points (312,092 duplicate bytes). Existing docs worktree and PR #42 preserved.
- Equity test invocation initially omitted DATA_ROOT and failed collection; rerun
  with an explicit task-owned external DATA_ROOT, matching the repository CI.
