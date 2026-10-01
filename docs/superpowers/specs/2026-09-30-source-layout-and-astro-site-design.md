# Source layout and bilingual Astro site design

Date: 2026-09-30

## Goal

Make the public competition repository easier to navigate and maintain by placing Python runtime packages in a conventional `src/` layout and replacing the hand-written one-page Pages site with a statically generated bilingual Astro site. English remains the primary language; Simplified Chinese is available as a secondary locale. The site remains suitable for GitHub Pages and contains only reviewed public project information.

## Current state

- Python runtime packages live at repository root in `adapters/`, `apps/`, `packages/`, and `strategies/`.
- `pyproject.toml` discovers those root-level packages and configures pytest to import from the repository root.
- The Pages source is a single static HTML page and stylesheet in `site/`; its workflow uploads `site/` directly.
- Python command-line tools live in `scripts/`, including the Pages content checker and strategy/backtest launchers.
- The repository has a Paper-first execution boundary. This design does not change trading behavior, provider integrations, or competition strategy.

## Options considered

1. **Keep plain HTML/CSS.** This has no Node toolchain and is suitable for a single page, but bilingual pages and future content require manual duplication and link maintenance.
2. **Use Astro for the site (selected).** Astro statically generates pages, supports locale routing, and can emit a site for GitHub Pages without requiring client-side JavaScript for the current content. It adds a Node build toolchain, which will be isolated to the website.
3. **Use Hugo.** Hugo is a strong fit for a large Markdown-centered documentation site. The current site is a project portal with a designed landing page and planned evidence summaries, so Astro's component model is a better fit.

## Repository layout

Move production Python packages under the repository-root `src/` while preserving their import names:

```text
src/
  adapters/
  apps/
  packages/
  strategies/
  competition_tools/
tests/
docs/
schemas/
config/
site/
  src/
    pages/
      index.astro          # English default route: /
      zh-CN/index.astro    # Simplified Chinese route: /zh-CN/
  public/
  astro.config.mjs
  package.json
  package-lock.json
```

All maintained Python command-line tools move from `scripts/` to `src/competition_tools/`, including the Pages content checker and strategy/backtest launchers, so Python application and tool code stays under the Python `src/` tree. Tests, documentation, JSON schemas, configuration, GitHub workflows, and static site source remain in conventional top-level locations. The phrase “all code under src” applies to application/runtime source: Python code uses root `src/`, and Astro source uses Astro's required `site/src/`; tests and deployment configuration do not move into either source tree.

## Python packaging and imports

- Configure setuptools package discovery with `where = ["src"]` and include the existing `adapters*`, `apps*`, `packages*`, and `strategies*` namespaces plus `competition_tools*`.
- Configure pytest to import from `src/` and keep tests under `tests/`.
- Update workflows and developer commands for all moved tools and source paths.
- Ensure CI installs the project in editable mode (or an equivalent package-aware setup) before tests and import checks. Verify imports from outside the repository root so tests cannot pass only because of the working directory.
- Keep schemas, runtime config, and competition documentation outside the Python package unless an existing package already treats them as package data; this migration does not change their ownership or contents.

## Astro site and localization

- Keep the public website source in `site/` and generate the deployable static output in `site/dist/`.
- Use Astro static output and its locale routing with English as the default locale and Simplified Chinese at `/zh-CN/`.
- Provide a visible language switcher on both localized pages. Preserve equivalent page destinations when switching languages.
- Configure the project `site` URL and repository `base` path for `runchengxie.github.io/2026-quant-competition/`, and verify direct navigation to both locale routes on GitHub Pages.
- Keep the current project overview, organizer rule links, strategy-candidate status, and publication-status notice. Do not publish positions, live performance, exact private strategy parameters, raw provider data, credentials, or account details.
- Translate visible page content into Simplified Chinese while keeping English canonical and complete. Internal research and project documentation remains English as already requested; this website localization does not duplicate internal documents.
- Do not add a client-side framework or runtime data/API fetching. Pages remain build-time static.

## CI, Pages, and local verification

- Python CI continues to run lint, formatting, tests, compilation/import checks, and secret checks without external service credentials.
- Pages CI installs the pinned Node dependencies, runs the Astro production build, runs the content disclosure checker against source and generated output, and uploads only `site/dist/`.
- The deployment job remains restricted to successful pushes to the public default branch (plus the existing manual deployment path); pull requests build and check but never deploy.
- Provide documented local commands for Python checks and `npm ci` / Astro build. No GitHub Actions minutes are needed for local verification.
- Verify generated links and assets under the repository base path, both locales, mobile layout, and that no forbidden/private content appears in the generated artifact.

## Migration safety

- Preserve Python import paths (`packages.contracts`, `adapters.ibkr`, and others) so callers and handoff interfaces do not change.
- Move files without changing runtime behavior; use focused commits or a focused PR so path changes are reviewable.
- Update `AGENTS.md` organization guidance and all documented commands that refer to old top-level Python paths.
- Do not copy quant-platform source or add a local-path dependency as part of this work.
- Do not combine AIVIX endpoint investigation, Index One strategy logic, or IB Gateway recovery with this repository-structure/site migration.

## Acceptance criteria

1. All maintained Python application/runtime and repository CLI tool sources are under root `src/`; tests remain under `tests/`.
2. Existing public Python import namespaces continue to work after installation.
3. Local and CI Python checks pass with the src layout, including an import check run outside the repository root.
4. Astro builds a static English home page and a Simplified Chinese page, each with working locale navigation.
5. The Pages workflow publishes only the generated `site/dist/` after successful build and content checks.
6. Both locale routes and their assets work under the GitHub Pages repository base path, and generated content passes the disclosure checker.
7. No provider secrets, credentials, account details, positions, or unreviewed performance figures appear in source or generated Pages output.

## Documentation references

- Astro i18n routing: https://docs.astro.build/en/guides/internationalization/
- Astro deployment to GitHub Pages: https://docs.astro.build/en/guides/deploy/github/
- GitHub Pages custom workflows: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
