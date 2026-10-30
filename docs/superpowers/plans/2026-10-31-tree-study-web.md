# Tree study website implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement the coupled contract and presentation task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Publish a reviewed, bounded aggregate of the completed retrospective tree study on current US strategy/factor pages.

**Architecture:** Root stdlib validates saved research before a closed projection. An independent publication validator pins the reviewed aggregate. Astro consumes it using bilingual catalogs and a small isolated filter controller; existing historical snapshots stay unchanged.

**Tech Stack:** Existing Python 3.12, Astro, JavaScript and Playwright; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-31-tree-study-web-design.md`

## Global constraints

- Read-only saved research; zero new fits, acquisitions, broker or ACL/data-directory changes.
- Public data allowlist only; reject paths, identifiers, predictions, duplicate fields, nonfinite numbers and extra keys.
- Bind all 432 matched identities, eight new model rows and exact source/protocol/parent hashes. Preserve null comparisons and blocked counts.
- Default English plus Chinese catalogs; readable mobile/no-JS tables, existing theme, historical snapshots unchanged.

## Review focus

- Forged aggregate hash/counts or swapped horizon/window/fee/buffer rows must fail validation.
- One missing account makes its comparison unavailable; never plot or label it as zero return.
- Equal-weight reference always uses buffer zero; other references match buffer.
- Filters must not mix rows from different windows/horizons or imply independent trials.
- Built HTML must embed exactly reviewed facts and keep six gaps and exposed-window limits visible.

### Task 1: coupled publication and reader presentation

Files: new `tree_study_projection.py`, `tree_study_publication.py` under root evaluation, closed schema under `schemas/research`, public aggregate under `site/src/data`, new Astro component/catalogs/controller/tests and minimal existing view integration, Pages checker and bilingual research docs.

- [x] Write failing contract tests for extra/private fields, altered identities/counts/returns, duplicates/nonfinite JSON and reviewed hash.
- [x] Implement explicit saved-result verification/projection and closed aggregate parsing; generate private candidate without rerunning models.
- [x] Write failing UI tests for matched selectors, unavailable comparisons and both locales/mobile/no-JS.
- [x] Implement the latest-study section on US strategies/factors and preserve historical files.
- [x] Run targeted Python/JS/browser/build/Pages checks, retain actual logs/screenshots and review the public candidate.
- [x] Commit reviewed implementation; root coordinator handles PR, combined checks, integration, deployment and cleanup.

## Execution authority

The user said “然后也帮我推进一下网页的呈现” after the concrete proposed existing-column presentation. This approves that scope; routine implementation choices above are coordinator decisions. Data migration and temporary ACL access are outside this task.
