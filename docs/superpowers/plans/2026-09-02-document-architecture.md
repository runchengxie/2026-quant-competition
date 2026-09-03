# 2026 Competition Document Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the competition documentation, convert the two operational PDFs to Markdown, and remove duplicated analysis content.

**Architecture:** Preserve source PDFs in `docs/sources`, place operational conversions in `docs/operations`, and separate competition interpretation from strategy design under `docs/competition` and `docs/strategy`.

**Tech Stack:** Markdown, PowerShell file operations, available PDF text extraction tooling.

**Spec:** `docs/superpowers/specs/2026-09-02-document-architecture-design.md`

## Global Constraints

- Preserve all original PDFs.
- Do not change rules or substantive strategy conclusions.
- Use stable English filenames for moved and converted files.
- Verify file existence, Markdown readability, and README links after edits.

---

### Task 1: Create the documentation layout

**Files:**
- Create: `docs/competition/`, `docs/strategy/`, `docs/operations/`, `docs/sources/`
- Move: existing rules and analysis files into their target locations

- [ ] Move `rules.md` and `rules.pdf` to `docs/competition/rules.md` and `docs/sources/rules.pdf`.
- [ ] Move `competition-analysis.md` to `docs/competition/competition-analysis.md`.
- [ ] Move `2026-competition-strategy-analysis.md` to `docs/strategy/strategy-analysis.md`.
- [ ] Move the two Chinese PDFs to their stable English names under `docs/sources/`.

### Task 2: Convert operational PDFs

**Files:**
- Create: `docs/operations/ibkr-simulated-account-guide.md`
- Create: `docs/operations/team-token-guide.md`

- [ ] Extract text from each source PDF with page boundaries retained.
- [ ] Convert recognizable title, heading, list, table, URL, and code-like content to Markdown.
- [ ] Add source filename and conversion note at the top of each Markdown file.
- [ ] Mark any image-only or layout-dependent content explicitly instead of inventing text.

### Task 3: Remove analysis duplication

**Files:**
- Modify: `docs/competition/competition-analysis.md`
- Modify: `docs/strategy/strategy-analysis.md`

- [ ] Keep competition rules, account, schedule, scoring, awards, and confirmation checklist in the competition document.
- [ ] Keep strategy positioning, alpha, portfolio construction, validation, metrics, and deck guidance in the strategy document.
- [ ] Replace repeated strategy descriptions with a short cross-reference.
- [ ] Replace repeated competition background with a short cross-reference.

### Task 4: Update the project entry point

**Files:**
- Modify: `README.md`
- Create: `docs/competition/schedule-and-checklist.md`
- Create: `docs/strategy/strategy-deck-outline.md`

- [ ] Update the tree, file descriptions, and reading order.
- [ ] Extract the actionable confirmation checklist into its own document while retaining a link from the competition analysis.
- [ ] Extract the deck page outline into its own document while retaining a link from the strategy analysis.

### Task 5: Verify the reorganization

- [ ] List all files recursively and confirm the target tree.
- [ ] Search for old filenames and broken relative links.
- [ ] Confirm all Markdown files begin with readable Markdown and contain no replacement-character corruption.
- [ ] Confirm source PDFs still exist and have non-zero size.
