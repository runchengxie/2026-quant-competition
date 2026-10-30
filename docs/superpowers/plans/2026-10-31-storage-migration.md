# Storage Namespace Migration Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans, TDD and independent final review. The user approved implementation and location-only local cutover on 2026-10-31.

**Goal:** Select and migrate the canonical project data directory without changing historical evidence or resetting budgets.

**Architecture:** A stdlib project-location resolver selects one canonical root, handles explicitly recorded historical locations and coordinates cross-root write guards. Independently packaged leaf clients share the same file/env contract without sibling imports.

**Tech Stack:** Python 3.12, pytest, native PowerShell for the actual move and task/config location updates.

**Spec:** [Approved migration design](../specs/2026-10-31-storage-namespace-migration-design.md).

## Global constraints and interfaces

- Keep workspace `DATA_ROOT`, private configuration namespace, schema IDs and historical provider identities unchanged.
- `GLOBAL_MARKET_RESEARCH_DATA_ROOT` and optional workspace `project_data_root` select an explicit direct-child project root. No root junction or symlink compatibility workaround.
- Existing legacy-only installation selects legacy; fresh/new-only selects `global-market-research`; ambiguous dual roots fail unless explicitly selected.
- Team v1 retains its three fields and workspace-root meaning. Team v2 adds explicit `project_data_root`. `TeamConfig.storage_root` exposes selected storage, and child environments receive it explicitly.
- Migration receipt `.storage-migration.json` binds exact sibling old/new roots, completed filesystem move and inventory digest; location mapping applies only to known absolute location fields.
- Cross-root guard checks and one shared workspace-level lock prevent old/new aliases from reserving the same protocol/input or paid authorization concurrently. Locks never erase durable attempt records.
- Historical source/input/receipt bytes and consumed reservations remain unchanged. Runtime path changes never confer research acceptance.

## Review focus

- Existing marker under an alternate root must prevent new attempts, including explicit-root changes.
- Both roots, malformed migration receipt, links and traversal must fail closed.
- Moved historical owner/output paths must map consistently without modifying records.
- Config defaults and independent package roots must agree on Windows and Linux.
- Cutover must preserve every retained regular file and distinguish runtime configuration from historical artifacts.

## Task 1: Root selection and guard compatibility

Files: new `src/competition_tools/project_storage.py`; new root tests; changes to team config/process/data/run, Gateway log-root validation, Databento authorization, reservation known-path readers, and independent leaf storage/path/guard clients.

- [ ] Write failing root-selection, location-mapping and cross-root marker/lock tests; observe missing module failure.
- [ ] Implement `project_root(data_root, explicit=None)`, `relocated_path(path)` and coordinated guard helper with strict path validation and stable errors.
- [ ] Add team v2 and `storage_root`, preserve v1 parsing; update all active data decisions and child environment propagation. Preserve provider/config identity strings.
- [ ] Add independent leaf resolver clients and known reservation location mapping, preserving frozen source snapshots and old protocol defaults.
- [ ] Exercise legacy/new/ambiguous configurations, mapped historical records and consumed guard races; run affected root/leaf suites, Ruff and boundaries.
- [ ] Update bilingual reader/retention guidance; independent review, required CI and merge compatibility work before local cutover.

## Task 2: Retained local cutover

Files: private inventories/scripts under the configured owner retention area; inventoried local path settings/task actions only.

- [ ] Export task definitions and mutable path settings privately. Record next triggers and active consumers; do not run tasks or change trading behavior.
- [ ] Seal no-follow regular-file hashes and link metadata with an explicit exclusion for inventory outputs. Preserve unknown/external links and archived fixture semantics.
- [ ] Rehearse rollback and location/guard checks on synthetic fixtures; confirm destination absent and safe writer-free interval.
- [ ] Move exact configured sibling directory once using native PowerShell. Update only inventoried mutable paths and task action location fields; retain old bytes and recovery records.
- [ ] Verify full file hashes, selected roots, markers, saved reports, task construction and moved runtime environments before enabling new writes.
- [ ] Record actual cutover status, remaining blocked evidence and rollback limits. Clean task-owned branch/worktree only after integration and verification.

## Execution ledger

- Baseline `2cef103`; design commit `7988eff`. Inventory found 666,759 regular files, 12,908,366,984 bytes and 33,210 reparse links. Inventory does not authenticate providers or hash all payloads yet.
- Ruling: storage migration is delivered before the separately approved tree study. Scientific source digests change with leaf path code; do not rebind any consumed parent protocol.
