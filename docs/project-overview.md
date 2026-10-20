# Project structure and current limits

[简体中文](project-overview.zh-CN.md) · [Documentation](README.md)

## How the parts fit together

Research prepares data, tests strategy ideas and writes reports. Execution reads an explicit target portfolio, checks it and works out what would need to change from current holdings. Research reports are not order instructions.

| Directory | Responsibility |
| --- | --- |
| `research/equity-lab` | Daily equity experiments and the six-market international diagnostic |
| `research/crypto-mm` | Crypto daily experiments and order-book market-making simulation |
| `research/platform-compare` | Local cash/share accounting, comparisons and five-market next-open experiments |
| `scripts/windows` | Paper Gateway operational wrappers |
| `config` and `schemas` | Configuration templates and data formats |
| `src/competition_tools` | Setup, data preparation, evaluation and report checks |
| `src/packages` | Target definitions, market rules, risk checks, audit and reconciliation |
| `src/strategies/nira` | Read externally produced Nira target files |
| `src/adapters` | Broker and provider integrations |
| `src/apps/execution_runner` | Runner configuration and execution flow |
| `site` | Bilingual project website |
| `tests` | Root package checks |

Research packages have separate dependencies and lockfiles. All three run without installing external quant frameworks. Accounting code derived from the former framework retains Apache-2.0 licensing and its source inventory; research adapters keep their scoped licenses.

The installed team CLI runs as `python -m competition_tools.team`. Follow the [quickstart](operations/team-quickstart.md) for its external bootstrap environment. Full package boundaries are in [architecture](architecture.md).

## Execution details

The research-to-execution handoff uses versioned `targets.json` and `lineage.json` files. The runner does not import external research-workspace or Nira source code.

Paper is the default execution environment. Programmatic `RunnerSettings` and the settings resolver default to `dry_run=false`, so callers must explicitly set `dry_run=true` when checking without submission. Preflight requires both Paper and dry-run. Read the [release checks](operations/release-checks.md) before broker operations.

Current execution accepts v1 targets. The published v1 JSON schema supports JP/US, while runtime normalization also recognizes HK; this discrepancy is unresolved. The independent [international v2 target design](strategy/target-manifest-v2.md) describes equity, ETF and futures identity but is not the current execution contract. Paper submission, cancellation, fill, restart and reconciliation still require supervised verification.

## Research status

The team is comparing a Hong Kong point-in-time fundamental/ranking portfolio and a U.S. ETF idea using AIVIX crypto sentiment. Neither has been finalized or registered for the competition. Data rights, out-of-sample evidence, account permissions and supervised Paper behavior still need validation.

The [24-result strategy inventory](research/strategy-validation-2026-10-19.md) and [expanded-data evaluation](research/data-expansion-and-evaluation.md) describe different experiment sets. Keep their dates and limitations with the results. Neither demonstrates a complete data-to-order system or future profitability.

## Data and private settings

Keep input data, model files, generated reports and runtime logs outside source under the configured data root. Keep private settings and credentials outside the checkout too. See [private configuration and providers](operations/environment-and-providers.md).

Competition dates and account requirements live in the [rules summary](competition/rules.md). The organizer's latest notices take precedence.
