# 2026 Quant Competition

Research and execution infrastructure for the 2026 Hong Kong quantitative trading competition.

## Project scope

This repository brings together competition research, data and account guidance, strategy candidates, and a Paper-first execution service. Research hands off versioned `targets.json` and `lineage.json` artifacts to the execution boundary; the runner does not import the separate `research-workspace` or Nira source code.

The execution path validates target portfolios, calculates the differences from current holdings, and supports IBKR Paper execution. Defaults remain `environment=paper` and `dry_run=true`.

## Strategy candidates

The team is comparing two research directions:

- A Hong Kong Point-in-Time fundamental and cross-sectional ranking portfolio.
- A U.S. ETF portfolio that uses AIVIX crypto sentiment as a signal.

The competition strategy has not been selected or registered. The candidates still need comparison against competition eligibility, data entitlements, out-of-sample evidence, and supervised Paper execution. AIVIX and Index One access and the integration method also require validation.

## Repository map

```text
2026-quant-competition/
├── README.md
├── docs/                    # competition, strategy, and operations material
├── src/
│   ├── packages/            # contracts, audit, reconciliation, and policies
│   ├── strategies/nira/     # external targets.json handoff only
│   ├── adapters/            # Nautilus boundary and IBKR event mapping
│   ├── apps/execution_runner/ # Paper-first runner configuration
│   └── competition_tools/   # repository CLI tools
├── site/                    # bilingual GitHub Pages site
└── tests/                   # unit and integration tests
```

## Competition dates

According to the organizer's public rules published on 2026-09-23, all times below are Hong Kong time:

- Registration closes: 2026-10-23 at 23:59.
- Trading period: 2026-10-26 at 00:00 through 2027-01-27 at 06:00.

See the [public competition rules](https://fundconnecthk.com/quant-league/legal/competition-rules/) and the [local rules summary](docs/competition/rules.md) for details. The organizer's latest notices take precedence.

## Start here

1. Read the [competition rules summary](docs/competition/rules.md) and [pre-competition checklist](docs/competition/schedule-and-checklist.md).
2. Review the [competition analysis](docs/competition/competition-analysis.md) and [strategy research](docs/strategy/strategy-analysis.md).
3. Review the operational guides and [release checks](docs/operations/release-checks.md) before running the Paper workflow.

## Development checks

The GitHub Actions workflow uses Python 3.12 and the committed `uv.lock` to run Ruff, the test suite, bytecode compilation, and a full-history secret scan. It does not connect to provider APIs or IB Gateway. The GitHub Pages site is built with Astro and Node.js 24; English is the default language and Simplified Chinese is available at `/zh-CN/`.

Run the Python checks locally with `uv sync --locked --extra test --extra ibkr`, then `uv run --locked ruff check .`, `uv run --locked pytest -q`, and `uv run --locked python -m compileall -q src`. The Pages workflow additionally checks formatting and scans the Astro source and generated output for unexpected files and sensitive values.

### Build the website locally

```powershell
npm --prefix site ci
npm --prefix site run build
uv run --locked python -m competition_tools.check_pages_content --source-dir site --built-dir site/dist
```

The generated static site is in `site/dist/`. The Pages workflow publishes that directory after the content checks pass.

## Research and safety notes

Competition statements and strategy material are research notes, not investment, legal, or compliance advice. No strategy result should be described as verified broker execution without supporting Paper evidence. Never commit `.env.local`, credentials, account information, order logs, raw provider responses, or run artifacts.
