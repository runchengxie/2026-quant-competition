# Daily Research Evidence Gaps Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task with TDD and a fresh whole-branch review.

**Goal:** Reproducibly verify existing IBKR daily snapshots and report six unverified research requirements.

**Architecture:** A stdlib API and CLI reuse daily manifest verification. A closed report schema and exclusive external output keep diagnostic completion separate from research acceptance.

**Tech Stack:** Python 3.12, pytest, JSON Schema (tests only).

**Spec:** [Approved design](../specs/2026-10-31-daily-research-evidence-gaps-design.md).

## Global Constraints

- Support existing IBKR daily v2 US/HK manifests only; do not read connection configuration.
- Always report blocked research status; no acquisition, broker, owner-trust or strategy changes.
- Preserve old contracts and APIs; no new production dependency.
- Require explicit expected manifest hash and new external output; never overwrite inputs or reports.

## Review Focus

- Unrecorded or mutated payload must fail before output publication.
- Duplicate/nonfinite JSON and unsupported producer metadata must fail without private-path disclosure.
- Concurrent output creation must preserve the winning file.
- Manifest or receipt mutation during verification must fail.
- Caller-supplied trust flags must not permit promotion.

## Task 1: API, CLI and closed contract

Files: create `src/competition_tools/datasets/research_evidence.py`, `schemas/research/daily-research-evidence-gap.v1.schema.json`, and `tests/competition_tools/datasets/test_research_evidence.py`.

- [x] Write a synthetic complete daily snapshot fixture and tests for exact schema fields, six blockers, US/HK, hash bindings and CLI success.
- [x] Run focused pytest; require failure because the module is absent.
- [x] Implement `audit_daily_research_evidence(manifest_path: Path, expected_sha256: str) -> dict`, `main(argv=None) -> int`, strict loading, producer validation and exclusive publication.
- [x] Add integrity, malformed JSON/spec, race/mutation, symlink/unsafe destination, no-overwrite and assertion-upgrade tests; observe failures before any required fixes.
- [x] Run focused tests, existing dataset/acceptance/readiness regression tests, Ruff and import boundaries; commit implementation.

## Task 2: Reader guidance and retained verification

Files: update bilingual `docs/research/datasets*`, `docs/research/research-acceptance*`, and `docs/quant-series-inspiration-audit*`.

- [x] Document command, exit semantics, six required evidence classes and limited producer scope in both languages.
- [ ] Generate private reports for the two retained real manifests, without replay or network acquisition; record source revision and checks in private retention inventory.
- [ ] Run full root pytest and required CI. Obtain independent whole-branch review and address findings.
- [ ] Verify current target result, merge reviewed PR under standing authorization, verify merged main and Pages, remove only task branch/worktree, retain evidence.

## Execution ledger

- Approved by user to implement on 2026-10-31. Implementation proceeds serially because all tasks share the report contract.
- Existing production research environment lacks pytest. Use a separate task test environment; never modify that runtime.
- Focused command suite: 38 passed. Dataset/acceptance/readiness regression: 212 passed before the final metadata strengthening; required CI will validate the final combined result.
- Review found malformed matching metadata could pass the reused verifier. A failing test reproduced this; the new command now validates metadata types, zoned timestamps and receipt agreement. Existing APIs remain unchanged. Independent re-review found no blocker.
- Ruling: test data uses the configured external data root because home-directory temporary paths are rejected by existing source-tree protections. Do not relax those protections.
