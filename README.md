# 2026 Quant Competition

[Project site / 项目网站](https://runchengxie.github.io/2026-quant-competition/)

Research and execution infrastructure for the 2026 Hong Kong quantitative trading competition.


[International offline experiments](docs/research/international-experiments.md)

## Project scope

This repository brings together competition research, data and account guidance, strategy candidates, and a Paper-first execution service. Research hands off versioned `targets.json` and `lineage.json` artifacts to the execution boundary; the runner does not import the separate `research-workspace` or Nira source code.

The execution path validates target portfolios, calculates the differences from current holdings, and supports IBKR Paper execution. Paper is the default environment. The programmatic `RunnerSettings` and resolver default to `dry_run=false`; explicitly set `dry_run=true` for validation without submission. Preflight requires both Paper and dry-run.

The independent [international v2 target contract](docs/strategy/target-manifest-v2.md) describes ETF, equity and futures identity. Current execution remains v1-only. See the [latest integration status](docs/operations/integration-readiness-2026-10-02.md) for actual provider, historical-data and local validation evidence.

## Offline research

Start with the [team quickstart](docs/operations/team-quickstart.md) ([简体中文](docs/operations/team-quickstart.zh-CN.md)) for a single-clone setup. `python -m competition_tools.team --help` requires Python 3.12 and the installed root package. Default setup installs isolated core environments and runs synthetic equity/crypto demos without quant framework packages. Accounting comparison remains an optional profile.

The two baseline [offline research packages](research/README.md) provide synthetic crypto market-making and daily equity backtest experiments. They have separate dependencies, tests and MIT licenses. Their results are not execution commands, verified live trading, or evidence of competition eligibility.

The [2026-10-19 strategy inventory and validation](docs/research/strategy-validation-2026-10-19.md) records 24 fixed-input diagnostics, current provider probes, limited stock coverage and archived crypto replay results. The [Chinese version](docs/research/strategy-validation-2026-10-19.zh-CN.md) and Pages use the same reviewed aggregate facts. These experiments do not establish a complete data-to-order system.

The [standalone dataset tools](docs/research/datasets.md) ([简体中文](docs/research/datasets.zh-CN.md)) acquire checked public spot daily archives or import explicit licensed files. The [expanded-data evaluation](docs/research/data-expansion-and-evaluation.md) ([简体中文](docs/research/data-expansion-and-evaluation.zh-CN.md)) separates new retrospective results from the original snapshot, documents the fixed crypto pool and records the missing historical S&P500 prerequisites.

The opt-in [input and experiment acceptance guide](docs/research/research-acceptance.md) explains exact-byte receipts, diagnostic checks and blocked research promotion. It adds no engine replacement, broker wiring or new public result snapshot.

## Strategy candidates

The team is comparing two research directions:

- A Hong Kong Point-in-Time fundamental and cross-sectional ranking portfolio.
- A U.S. ETF portfolio that uses AIVIX crypto sentiment as a signal.

The competition strategy has not been selected or registered. The candidates still need comparison against competition eligibility, data entitlements, out-of-sample evidence, and supervised Paper execution. AIVIX and Index One access and the integration method also require validation.

## Repository map

See [architecture and ownership](docs/architecture.md) ([简体中文](docs/architecture.zh-CN.md)) for package boundaries. The CLI lives in `src/competition_tools/team` and runs as `python -m competition_tools.team` after installation. Follow the quickstart for an external bootstrap environment.

```text
2026-quant-competition/
├── README.md
├── docs/                    # competition, strategy, and operations material
├── scripts/windows/         # Paper Gateway operational wrappers
├── config/                  # runtime configuration and templates
├── schemas/                 # artifact and handoff JSON schemas
├── src/
│   ├── packages/            # contracts, audit, reconciliation, and policies
│   ├── strategies/nira/     # external targets.json handoff only
│   ├── adapters/            # Nautilus boundary and IBKR event mapping
│   ├── apps/execution_runner/ # Paper-first runner configuration
│   └── competition_tools/   # repository CLI tools
├── research/                # independent offline experiments, own locks/tests/licenses
├── site/                    # bilingual GitHub Pages site
└── tests/                   # unit and integration tests
```

## Competition dates

According to the organizer's public rules dated 2026-10-13, checked on 2026-10-18, all times below are Hong Kong time:

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

## Research and safety notes

Competition statements and strategy material are research notes, not investment, legal, or compliance advice. No strategy result should be described as verified broker execution without supporting Paper evidence. Never commit `.env`, credentials, account information, order logs, raw provider responses, or run artifacts.

## Local environment configuration

Copy `.env.example` to `.env` and fill in your private values. Keep `.env` outside Git; `.env.example` contains public placeholders only. Use a single `.env` file rather than a separate `.env.local`. The runner reads process environment variables and does not automatically load dotenv files; load the required values into the process environment before starting it.

### AIVIX / Cryptoracle backup key

Set `CRYPTORACLE_API_KEY` and optionally `CRYPTORACLE_API_KEY_BACKUP` in `.env`, then load them into the process environment. The [Cryptoracle client](src/adapters/cryptoracle/client.py) reads both keys and `CRYPTORACLE_API_BASE_URL`:

Use `CRYPTORACLE_API_BASE_URL=https://service.cryptoracle.network/openapi`. The client also adds `/openapi` when an older configuration contains only the official service host; custom URLs keep their configured paths.

```python
from adapters.cryptoracle import CryptoracleClient

client = CryptoracleClient.from_environment(timeout=15.0)
# Read-only token discovery, verified against the service on 2026-10-12.
data = client.post("/v2.1/coin/list", {"timeType": "1h"})
```

Each call tries the primary key first. HTTP 401, 403 or 429, or JSON business code `202` (invalid API key), triggers one attempt with the backup key and the same query. Empty values, example placeholders and duplicate keys are skipped; a backup key can also be used alone. Other HTTP failures, network errors and invalid JSON do not trigger a key change. A non-200 integer JSON business code raises `CryptoracleAPIError`; its `status_code` and `business_code` distinguish HTTP status from provider errors, which can arrive inside HTTP 200 responses. Error messages and settings representations omit credentials and provider error bodies. The client uses HTTPS and rejects redirects rather than forwarding keys to another host.

The client does not automatically load `.env` or select indicator endpoints. The [official API overview](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1) specifies the `/openapi` root, and the [authentication documentation](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1/authentication) specifies the `X-API-KEY` header. The [2026-10-12 validation](docs/operations/cryptoracle-validation-2026-10-12.md) confirms backup-key token discovery through both the configured proxy and direct networking, and invalid-key failover. Indicator/history entitlements and coverage remain unverified.

### Other providers

QuantZone is optional: fill both `QUANTZONE_ACCESS_KEY` and `QUANTZONE_SECRET_KEY` in your local `.env` when access is available. The SDK requires `access_key` and `sign_secret` respectively; a single `QUANTZONE_API_KEY` is insufficient. `QUANTZONE_API_BASE_URL` records the candidate service URL; no QuantZone adapter or authentication flow is implemented yet. These entries do not validate account entitlement or factor coverage.

See the [official QuantZone documentation](https://www.quantzone.tech/docs) for the paired credentials and SDK initialization. Use the service URL shown in your console.

Read-only provider and FX checks are recorded in the [2026-10-02 validation update](docs/operations/provider-fx-validation-2026-10-02.md). The approved USD price ledger is implemented in quant-platform; see the [2026-10-03 delivery and remaining integration](docs/operations/usd-ledger-delivery-2026-10-03.md) for its reviewed revision, public interfaces and synthetic evidence. The research consumer, legacy baseline calculation and broker execution have not changed.

The optional [standalone accounting comparison](docs/research/accounting-comparison.md) ([简体中文](docs/research/accounting-comparison.zh-CN.md)) retains legacy decisions and compares them with the competition-owned cash/share ledger, without external framework dependencies on synthetic HK/US inputs. Real daily inputs remain blocked without causal clocks, lots and FX metadata. The existing public snapshot is unchanged.
