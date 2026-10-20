# Development and website checks

[简体中文](development.zh-CN.md) · [Documentation](README.md)

Run these commands from the repository root. Set `DATA_ROOT` to an absolute directory outside the checkout before running tests. Resolve it from your workspace configuration or choose an explicit external directory. Keep environments and retained test output there.

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path $env:DATA_ROOT "2026-quant-competition/environments/dev"
```
## Python checks

The GitHub Actions workflow uses Python 3.12 and the committed `uv.lock` to run Ruff, the test suite, bytecode compilation, and a full-history secret scan. It does not connect to provider APIs or IB Gateway.

```powershell
uv sync --locked --extra test --extra ibkr
uv run --locked ruff check .
uv run --locked pytest -q
uv run --locked python -m compileall -q src
```

The baseline research packages have separate environments and checks; see the [research guide](../research/README.md). Optional ledger checks are in the [accounting guide](research/accounting-comparison.md).

## Build the website locally

The site uses Astro and Node.js 24. English is the default language and Simplified Chinese is available at `/zh-CN/`. The Pages workflow also checks formatting and scans source and generated output for unexpected files and sensitive values.

The bilingual homepage showcases the equity and crypto research paths with synthetic input previews, local demo commands, strategy context and the execution boundary. Its path switch changes the walkthrough without running backtests in the browser. Shared rendering keeps commands and sample values the same across locales; translated text lives in `site/src/i18n/`. Competition guidance remains linked as supporting context.

Appearance follows the system by default. The navigation offers Light, Dark and System choices and remembers the choice across both languages when browser storage is available. With JavaScript disabled, the system palette still applies.

```powershell
npm --prefix site ci
npm --prefix site run build
npx --prefix site playwright install chromium
npm --prefix site test
uv run --locked python -m competition_tools.check_pages_content --source-dir site --built-dir site/dist
```

The browser tests cover saved preferences, system changes, both locales, mobile layout, and text/table/chart contrast. Set `PAGES_TEST_OUTPUT` to a task directory under your configured `DATA_ROOT` to retain browser artifacts; otherwise they go to the system temporary directory. The generated static site is in `site/dist/`. The Pages workflow publishes that directory after the checks pass.
