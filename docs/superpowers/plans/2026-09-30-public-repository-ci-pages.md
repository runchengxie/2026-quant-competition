# Public Repository, CI, and Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prepare the current competition repository for public access with reliable GitHub CI and a sanitized GitHub Pages project site.

**Architecture:** Keep Python validation in GitHub Actions, build Pages from a dedicated static `site/` directory, and publish from `main` only. Perform a full history and release asset audit before switching repository visibility; use current official competition dates as the maintained source of truth. Translate all reader-facing documentation into English using the organizer's permission, and remove all original PDF release assets. Strategy research and provider API probes are a separate follow-up plan after this public-repository workstream.

**Tech Stack:** Python 3.12, uv, pytest, Ruff, GitHub Actions, GitHub Pages artifact deployment, static HTML/CSS.

**Spec:** `docs/superpowers/specs/2026-09-30-competition-publication-and-strategy-validation-design.md`

## Global Constraints

- Preserve the Python requirement `>=3.12,<3.13`.
- Do not place AIVIX, Index One, IBKR, or account credentials in Git, workflow logs, Pages, or artifacts.
- GitHub Actions uses mocks and local fixtures only; it must not connect to IB Gateway or external provider APIs.
- Repository code and Pages are public only after the history, release asset, and site content audit passes.
- Pages contains project context and sanitized results only; no positions, live performance, exact model parameters, raw provider data, credentials, or account details.
- Keep research code outside this execution repository; it crosses the boundary through versioned `targets.json` and `lineage.json` artifacts.
- Keep Paper defaults `environment=paper` and `dry_run=true`.
- Follow the repository's worktree-first, PR-first workflow and leave publication as the final release action.

## Review Focus

- Historical Git blobs and release assets may retain removed PDFs or credentials; the audit must inspect Git history and releases, not just the current tree.
- Pull requests from forks must not receive privileged secrets or write permissions; CI has no external credential dependency.
- Existing date references may disagree with the current official 2026-09-23 rule set; update maintained guidance and label old analysis as historical.
- Pages may accidentally include tracked artifacts that contain model details or account identifiers; build only from an explicit `site/` allowlist.
- GitHub Pages availability depends on repository visibility and account plan; verify the Pages deployment after the public switch.

---

### Task 1: Reconcile competition dates and public-facing references

**Files:**
- Modify: `README.md`
- Modify: `docs/competition/rules.md`
- Modify: `docs/competition/competition-analysis.md`
- Modify: `docs/competition/schedule-and-checklist.md`
- Modify: `docs/competition/competition-analysis.md`
- Modify: `docs/strategy/strategy-analysis.md`
- Modify: `docs/operations/competition-mvp-status.md`
- Modify: `config/competition-2026-hk.json`

**Interfaces:**
- Consumes: official rules version dated 2026-09-23 at `https://fundconnecthk.com/quant-league/legal/competition-rules/`.
- Produces: a public-source-only competition rules summary; consistent local dates (registration deadline 2026-10-23 23:59 HKT; competition 2026-10-26 00:00 through 2027-01-27 06:00 HKT); historical labels for older analysis; and current strategy-candidate status.

- [x] **Step 1: Create a rule reconciliation table** listing every stale date, claim, and local file against the official public rule page. Preserve dated historical conclusions with an explicit historical label.
- [x] **Step 2: Update the maintained rule summary and dependent schedule/configuration documents**; do not change strategy or execution behavior in this task.
- [x] **Step 3: Search for remaining stale dates and unsupported current-date claims.**

Run: `rg -n '2026-09-28|2026-12-29|2026\.09\.28|2026\.12\.29|September 28|December 29|September 18|September 14|September 25|September 27' README.md docs config`

Expected: remaining matches are either source-history notes explicitly marked historical or none.

- [x] **Step 4: Review the Markdown diff.** The translated documents will be committed together after the remaining publication checks.

### Task 2: Audit the public repository history, release assets, and pages inputs

**Files:**
- Create: `docs/operations/publication-audit-2026-09-30.md`
- Inspect: all reachable Git blobs, GitHub release assets, current tracked files, `.env.example`, and proposed `site/` files.

**Interfaces:**
- Consumes: repository history and release `reference-pdfs-2026-09`.
- Produces: a reviewable inventory of inspected sources, findings by path and commit/release, and an explicit disposition for each finding. Never copy credential values into the audit log.

- [x] **Step 1: Inventory reachable commits, tracked files, release tags, and release asset names.** Record coverage counts and locations without printing secrets.
- [x] **Step 2: Run a full-history secret-pattern scan** and classify PDF release assets for removal. `.env.local` remains private local input even though it is ignored.
- [x] **Step 3: Classify findings** and record the authorization and removal disposition.
- [x] **Step 4: Record findings and dispositions** in `docs/operations/publication-audit-2026-09-30.md`; exclude account IDs, private personal details, token values, and raw market data.
- [x] **Step 5: Obtain a clean audit disposition before making repository visibility public.** No history rewrite is currently indicated by the scan; final CI/review remains a release gate.

### Task 3: Add deterministic CI code checks

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: existing unit suite under `tests/`, project Python bounds, and uv lockfile.
- Produces: pull-request and `main`-push checks for dependency integrity, lint, tests, compile validation, and full-history secret scanning; no external API credentials are required.

- [x] **Step 1: Add Ruff to the project's test/development dependency group** and configure only rules that pass on the current codebase without broad unrelated cleanup.
- [x] **Step 2: Lock the dependency change** with `uv lock` and commit the lockfile with `pyproject.toml`.
- [x] **Step 3: Create a pull-request and main-push workflow** pinned to Python 3.12 and using `uv sync --locked --extra test --extra ibkr`; the IBKR adapter suite imports the optional broker package.
- [x] **Step 4: Add workflow steps** for `ruff check`, targeted `ruff format --check`, `pytest`, `python -m compileall -q adapters apps packages strategies`, and a full-history secret scan. Use read-only workflow permissions and no repository secrets.
- [x] **Step 5: Validate locally** with the same lint, targeted format, test, and compile commands. Ruff, pytest, compileall, and the Pages content check pass locally.
- [x] **Step 6: Commit** with `ci: add locked Python quality checks` (`4ea34d0`).

### Task 4: Create an explicit-allowlist static project site

**Files:**
- Create: `site/index.html`
- Create: `site/styles.css`
- Create: `scripts/check_pages_content.py`
- Create: `docs/operations/pages-content-policy.md`

**Interfaces:**
- Consumes: manually reviewed public facts and approved sanitized results only.
- Produces: static Pages content built exclusively from `site/`, with no automatic copying of `docs/`, `artifacts/`, `runs/`, or release PDFs.

- [x] **Step 1: Write a Pages content policy** enumerating allowed sections and prohibited content from the spec.
- [x] **Step 2: Create a responsive static project page** with project purpose, high-level strategy/execution architecture, current official competition dates, source links, and repository link.
- [x] **Step 3: Add only verified, sanitized historical/Paper results**; since no run passed review, the site states that results are not yet available for publication.
- [x] **Step 4: Add a recursive content check** that fails on secret-like patterns, account/order identifiers, symlinks, nested paths, and files outside the allowlist.
- [x] **Step 5: Review and commit** with `docs: add sanitized competition project site` (`151fbd4`); the recursive checker was tightened after review.

### Task 5: Configure Pages build and deployment

**Files:**
- Create: `.github/workflows/pages.yml`

**Interfaces:**
- Consumes: `site/` and the Task 4 content check.
- Produces: Pages artifact on main and deployment with least-privilege `pages: write` and `id-token: write` permissions; pull requests build/check but do not deploy.

- [x] **Step 1: Add a Pages build job** that runs the content check and uploads only `site/` as the artifact.
- [x] **Step 2: Add a main-only deployment job** using the official Pages actions, least-privilege job permissions, and a named environment. Deployment waits until the repository is public.
- [x] **Step 3: Run the content check locally; confirm the artifact source is only `site/`.**
- [x] **Step 4: Commit** with `ci: deploy sanitized site to GitHub Pages` (`4fd0447`); the deployment ref gate was tightened after review.

### Task 6: Review release gates and publish

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/pages.yml`
- Modify: `docs/operations/publication-audit-2026-09-30.md`

**Interfaces:**
- Consumes: clean publication audit, passing CI, and reviewed Pages artifact.
- Produces: public repository and deployed Pages site, then verified links and settings in the audit record.

- [ ] **Step 1: Confirm** audit disposition is clean, remote CI is green, the Pages artifact contains only `site/`, and no secrets appear in Actions logs or artifacts.
- [ ] **Step 2: Push the feature branch and open a PR**; request review and wait for all required Actions checks.
- [ ] **Step 3: Merge the reviewed PR** following repository policy.
- [ ] **Step 4: Change repository visibility to public and enable Pages** only after the previous gates pass.
- [ ] **Step 5: Verify** public repository access, Pages URL/HTTPS, latest Pages deployment, workflow permissions, branch protection or ruleset, and visible release assets.
- [ ] **Step 6: Record the resulting public URLs and settings** without adding private operational values; commit the final publication record.

### Follow-up workstream: AIVIX + Index One + IB Gateway strategy validation

Create a separate implementation plan after mapping the research workspace and validating account entitlements. The execution repository's current supported target schema is limited to `JP` and `US`; the candidate must first confirm that US ETF targets map correctly through market normalization and IBKR contract qualification. The follow-up plan must specify provider response models, point-in-time cutoff semantics, frozen target manifest, Index One weight reconciliation, three-way baseline comparison, and supervised Paper order lifecycle. Do not place provider API keys in the GitHub CI workflows or Pages site.
