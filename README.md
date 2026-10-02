# 2026 Quant Competition

[Project site / 项目网站](https://runchengxie.github.io/2026-quant-competition/)

Research and execution infrastructure for the 2026 Hong Kong quantitative trading competition.

## Project scope

This repository brings together competition research, data and account guidance, strategy candidates, and a Paper-first execution service. Research hands off versioned `targets.json` and `lineage.json` artifacts to the execution boundary; the runner does not import the separate `research-workspace` or Nira source code.

The execution path validates target portfolios, calculates the differences from current holdings, and supports IBKR Paper execution. Defaults remain `environment=paper` and `dry_run=true`.

The independent [international v2 target contract](docs/strategy/target-manifest-v2.md) describes ETF, equity and futures identity. Current execution remains v1-only. See the [latest integration status](docs/operations/integration-readiness-2026-10-02.md) for actual provider, historical-data and local validation evidence.

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

Competition statements and strategy material are research notes, not investment, legal, or compliance advice. No strategy result should be described as verified broker execution without supporting Paper evidence. Never commit `.env`, credentials, account information, order logs, raw provider responses, or run artifacts.

## Local environment configuration

Copy `.env.example` to `.env` and fill in your private values. Keep `.env` outside Git; `.env.example` contains public placeholders only. Use a single `.env` file rather than a separate `.env.local`. The runner reads process environment variables and does not automatically load dotenv files; load the required values into the process environment before starting it.

QuantZone is optional: fill both `QUANTZONE_ACCESS_KEY` and `QUANTZONE_SECRET_KEY` in your local `.env` when access is available. The SDK requires `access_key` and `sign_secret` respectively; a single `QUANTZONE_API_KEY` is insufficient. `QUANTZONE_API_BASE_URL` records the candidate service URL; no QuantZone adapter or authentication flow is implemented yet. These entries do not validate account entitlement or factor coverage.

See the [official QuantZone documentation](https://www.quantzone.tech/docs) for the paired credentials and SDK initialization. Use the service URL shown in your console.

Read-only provider and FX checks are recorded in the [2026-10-02 validation update](docs/operations/provider-fx-validation-2026-10-02.md). The approved USD price ledger is implemented in quant-platform; see the [2026-10-03 delivery and remaining integration](docs/operations/usd-ledger-delivery-2026-10-03.md) for its reviewed revision, public interfaces and synthetic evidence. The research consumer, legacy baseline calculation and broker execution have not changed.
