# Python src Layout and Astro Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task in the current session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move maintained Python sources into a root `src/` tree and publish a bilingual static Astro website through GitHub Pages.

**Architecture:** Preserve existing Python import namespaces under `src/`, package CLI utilities as `competition_tools`, and keep tests/docs/configuration at the repository root. Build the website from `site/src/` using Astro static output with English at `/` and Simplified Chinese at `/zh-CN/`; deploy only `site/dist/` after source and generated-output checks.

**Tech Stack:** Python 3.12, setuptools, pytest, Ruff, uv, Node.js (Astro-supported LTS), Astro static output, GitHub Actions Pages artifact/deploy actions.

**Spec:** `docs/superpowers/specs/2026-09-30-source-layout-and-astro-site-design.md`

## Global Constraints

- Python requires `>=3.12,<3.13`.
- Preserve import names such as `packages.contracts` and `adapters.ibkr`.
- Paper remains the default; this work does not add provider access or order behavior.
- English is primary and complete; Simplified Chinese is secondary at `/zh-CN/`.
- Static site source stays in `site/`; only generated `site/dist/` is deployable.
- No external credentials are available to CI; do not add secrets or provider calls.
- Keep test code under `tests/`, documentation under `docs/`, and deployment configuration under `.github/`.
- Do not copy `quant-platform` code or add a local-path dependency.

## Review Focus

- **Python import shadowing:** Verify imports resolve after changing the working directory outside the checkout; own this in Task 1.
- **CLI path assumptions:** Verify moved tools still find repository-relative schemas/configuration and preserve CLI help; own this in Task 1.
- **Pages base path:** Verify locale links and asset URLs include `/2026-quant-competition/`; own this in Task 2.
- **Generated disclosure scan:** Verify both locales and all generated files are scanned and forbidden content fails the build; own this in Task 3.
- **Static route behavior:** Verify `/` and `/zh-CN/` each resolve to the intended locale and locale switching preserves page identity; own this in Task 2.

---

### Task 1: Move Python sources into the root src layout

**Files:**
- Move: all tracked Python packages from `adapters/`, `apps/`, `packages/`, and `strategies/` to the matching `src/` paths.
- Move: `scripts/*.py` to `src/competition_tools/` and add `src/competition_tools/__init__.py`.
- Modify: `pyproject.toml`, `.github/workflows/ci.yml`, `.github/workflows/pages.yml`.
- Modify: `README.md`, `AGENTS.md`, `docs/operations/paper-preflight.md`, and any current operational docs containing executable old paths.
- Test: add `tests/test_source_layout.py` for installed importability and repository-relative resources.

**Interfaces:**
- Consumes: existing packages and CLI flags without changing their public import names or behavior.
- Produces: installable Python packages under `src/`; CLI modules `competition_tools.check_pages_content`, `competition_tools.run_global_etf_rotation`, `competition_tools.run_hk_baseline_backtest`, and `competition_tools.run_paper_preflight`.

- [ ] **Step 1: Add source-layout regression tests**

Add tests asserting that `packages.contracts`, `adapters.ibkr`, `apps.execution_runner`, `strategies.global_etf_rotation`, and `competition_tools` are importable from an editable install. Add a subprocess check that changes its working directory to a temporary directory before importing. Add a resource-path assertion for the Pages checker so it locates the repository's `site/` directory independent of current working directory.

- [ ] **Step 2: Run the new tests and confirm the expected failure**

Run: `uv run --extra test pytest tests/test_source_layout.py -q`
Expected: fail because the packages still live outside `src/` and `competition_tools` does not exist.

- [ ] **Step 3: Move packages and CLI tools**

Use `git mv` to preserve relative package contents under `src/{adapters,apps,packages,strategies}`. Move each Python file in `scripts/` into `src/competition_tools/`, create its `__init__.py`, and leave no maintained `.py` module in the old top-level paths.

- [ ] **Step 4: Configure packaging, tests, and workflows**

Set pytest `pythonpath = ["src"]`; set setuptools discovery `where = ["src"]` and include the four existing namespaces plus `competition_tools*`. Update Ruff format paths and compile paths. Update Pages workflow invocation to `uv run python -m competition_tools.check_pages_content`. Keep Python CI dependency installation locked and package-aware.

- [ ] **Step 5: Update active documentation and developer commands**

Change the repository tree in `README.md`, package locations in `AGENTS.md`, and current Paper preflight commands to `uv run python -m competition_tools.run_paper_preflight`. Search active docs for `python scripts/` and remove all obsolete executable references. Historical implementation plans may retain their original paths as records.

- [ ] **Step 6: Run source-layout tests and full Python checks**

Run: `uv run --extra test pytest tests/test_source_layout.py -q`
Expected: PASS, including the outside-checkout subprocess import.

Run formatting only on files covered by the existing repository gate, plus the new source-layout test; the repository's other Python files were not previously format-checked:

```powershell
uv run --extra test ruff format --check src/adapters/ibkr/events.py src/competition_tools/check_pages_content.py tests/test_source_layout.py
```

Run the test suite with the `ibkr` optional dependency enabled and a workspace-local pytest temp root:

```powershell
uv run --extra test --extra ibkr pytest -q --basetemp=.pytest-tmp-task1-final
```

Run: `uv run --extra test ruff check .` and `uv run python -m compileall -q src`.
Expected: all checks pass. Also run `uv run python -m competition_tools.run_paper_preflight --help` and each moved research CLI with `--help` to verify module invocation without loading input datasets.

- [ ] **Step 7: Commit the Python layout migration**

```bash
git add -A
git commit -m "refactor: move Python packages into src layout"
```

### Task 2: Build the English and Simplified Chinese Astro site

**Files:**
- Create: `site/package.json`, `site/package-lock.json`, `site/astro.config.mjs`, `site/tsconfig.json` if required by the selected Astro release.
- Create: `site/src/layouts/SiteLayout.astro`, `site/src/pages/index.astro`, `site/src/pages/zh-CN/index.astro`, and `site/src/styles/global.css`.
- Move or replace: current `site/index.html` and `site/styles.css` with equivalent Astro components and styles.
- Ignore: `site/node_modules/`, `site/.astro/`, and `site/dist/` in `.gitignore`.
- Test: add `tests/test_astro_site.py` to validate built routes, locale links, and base-prefixed assets.

**Interfaces:**
- Consumes: no runtime API; static copy and approved public links from the existing page.
- Produces: `site/dist/index.html` (English), `site/dist/zh-CN/index.html` (Simplified Chinese), static CSS/assets, and locale links between equivalent routes.

- [ ] **Step 1: Add Astro build-output tests**

Create `tests/test_astro_site.py` that reads only a built fixture/output directory and asserts English `lang="en"`, Simplified Chinese `lang="zh-CN"`, correct localized copy in each route, matching language-switch destinations, and asset URLs prefixed by `/2026-quant-competition/`.

- [ ] **Step 2: Run tests to confirm they fail without the Astro output**

Run: `uv run --extra test pytest tests/test_astro_site.py -q`
Expected: fail because the required generated route files do not exist.

- [ ] **Step 3: Add pinned Astro project and localized pages**

Create the site-local npm project and lockfile. Configure Astro with `site: "https://runchengxie.github.io"`, `base: "/2026-quant-competition"`, static output, locales `en` and `zh-CN`, default locale `en`, and no prefix for the default locale. Implement a shared layout and equivalent English/Simplified Chinese page content with a visible locale switcher. Keep the current rule link, strategy-candidate status, and no-results-yet notice. Do not include live performance or private strategy details.

- [ ] **Step 4: Build and pass route/output tests**

Run: `npm --prefix site ci; npm --prefix site run build`
Expected: Astro emits both locale routes into `site/dist/`.

Run: `uv run --extra test pytest tests/test_astro_site.py -q`
Expected: PASS for locale metadata, route links, and repository base-prefixed assets.

- [ ] **Step 5: Review generated content and responsive page**

Inspect `site/dist/index.html` and `site/dist/zh-CN/index.html`; run a local static server from `site/dist/` and verify desktop/mobile layout, direct locale navigation, and language switching. Confirm no API credentials, account details, positions, or performance figures are present.

### Task 3: Harden the Pages content check and deploy Astro output

**Files:**
- Modify: `src/competition_tools/check_pages_content.py`.
- Test: create `tests/competition_tools/test_check_pages_content.py`.
- Modify: `.github/workflows/pages.yml`, `.github/workflows/ci.yml`, `README.md`, `.gitignore`.

**Interfaces:**
- Consumes: explicit source and built-site paths.
- Produces: a zero exit status for an allowlisted, safe site and nonzero for unknown files, symlinks, or sensitive patterns; Pages artifact contains only `site/dist/`.

- [ ] **Step 1: Add checker behavior tests**

Test that source and generated paths are both scanned; allowed Astro source files and public static assets pass; unknown files and symlinks fail; credential/account/order patterns fail in both locales; and missing required English or Simplified Chinese route files fail.

- [ ] **Step 2: Run the checker tests to confirm failure**

Run: `uv run --extra test pytest tests/competition_tools/test_check_pages_content.py -q`
Expected: fail because the existing checker uses a fixed `site/` root and only allows the legacy HTML/CSS files.

- [ ] **Step 3: Implement explicit source/output checking**

Add required `--source-dir` and `--built-dir` CLI arguments to `competition_tools.check_pages_content`. Source allowlist: `astro.config.mjs`, `package.json`, `package-lock.json`, optional `tsconfig.json`, `src/**/*.astro`, `src/**/*.css`, and `public/**/*` with static image/font formats. Ignore generated/cache directories (`node_modules`, `.astro`, `dist`) during source traversal. Generated output must contain the English and Simplified Chinese route files plus HTML/CSS/JS and static image/font files. Scan file contents in both trees for the existing sensitive patterns. Reject symlinks and unrecognized source/output paths.

- [ ] **Step 4: Update Pages build and deploy workflow**

In `pages.yml`, install Python 3.12 and locked tool dependencies, install a Node LTS supported by the locked Astro version, run `npm ci --prefix site`, run the Astro production build, invoke the checker with source and built directories, and upload only `site/dist/`. Retain the current deploy guard: deploy only successful main pushes or explicit manual runs on a public repository; pull requests only build and check.

- [ ] **Step 5: Update ignore rules and local instructions**

Ignore `site/node_modules/`, `site/.astro/`, and `site/dist/`. Document Python local checks and the `npm --prefix site ci`, `npm --prefix site run build`, and checker commands in `README.md`.

- [ ] **Step 6: Run the complete local verification suite**

Run each command in order, stopping at the first failure:

```bash
uv run --extra test --extra ibkr pytest -q --basetemp=.pytest-tmp-final
uv run --extra test ruff check .
uv run --extra test ruff format --check src/adapters/ibkr/events.py src/competition_tools/check_pages_content.py tests/test_source_layout.py
uv run python -m compileall -q src
npm --prefix site ci
npm --prefix site run build
uv run python -m competition_tools.check_pages_content --source-dir site --built-dir site/dist
```

Expected: all Python tests/checks pass; both site routes build; content checker passes.

- [ ] **Step 7: Inspect artifact and workflow diff, then commit**

Verify the uploaded artifact path is exactly `site/dist/`, no generated files are tracked, no secrets or results were added, and Pages does not deploy from pull requests. Commit the focused website/workflow change:

```bash
git add -A
git commit -m "feat: publish bilingual Astro Pages site"
```

### Task 4: Final branch verification and review preparation

**Files:**
- Review: all changed Python, Astro, workflow, documentation, ignore, and lock files.

**Interfaces:**
- Consumes: completed Tasks 1–3.
- Produces: review-ready branch with locally verified Python and static-site builds.

- [ ] **Step 1: Run full verification from a clean build state**

Run the Task 3 verification commands after deleting only ignored generated `site/dist/`, `site/.astro/`, and local `site/node_modules/`, then reinstall with `npm ci`. Confirm clean reproducibility and that `git status --short` contains only intentional source changes.

- [ ] **Step 2: Review path references and public output**

Run `rg -n "python scripts/|scripts/check_pages_content|Traditional Chinese|zh-Hant" README.md AGENTS.md docs/operations .github site src tests` and resolve stale active references. Inspect both generated HTML pages and verify the disclosure checker.

- [ ] **Step 3: Prepare PR and defer merge/publication to the repository workflow**

Push the feature branch and open a PR against `main`; wait for CI and review. Do not merge or change repository visibility as part of this source/site migration.
