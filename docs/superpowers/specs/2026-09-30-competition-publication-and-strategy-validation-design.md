# Competition publication and three-provider strategy validation

Date: 2026-09-30

Repository name: `2026-quant-competition`. The organizer authorized English versions of the team reference guides; the user directed removal of all three release PDFs and approved public publication after review. Keep the repository private until the PR/CI gates pass, then publish the repository and Pages site.

## Intent and current state

The team wants to evaluate a US-listed ETF competition strategy that uses AIVIX/Cryptoracle data, Index One index calculation, and IB Gateway Paper execution. The team also wants this entire repository to become public, with GitHub CI code checks and a GitHub Pages site limited to project information and sanitized results. The candidate strategy is research, not yet the registered competition strategy.

The repository currently has a Hong Kong equity strategy as its documented main candidate. Its target handoff and Paper-first execution boundary exist, but a real Paper Gateway order-lifecycle smoke test and continuous Paper shadow have not been completed. There is no GitHub Actions workflow or Pages site in the tracked tree. The GitHub repository is currently private.

The official 2026-09-23 competition rules now state registration closes 2026-10-23 and trading runs 2026-10-26 00:00 through 2027-01-27 06:00 HKT. Several local documents still contain the older September–December schedule and must be corrected before publication or competition planning. Each team enters one strategy and one account. AIVIX award eligibility requires applying for and actually using the data through the team portal and explaining its contribution.

## Workstream A: public repository, CI, and Pages

1. Reconcile competition dates and rule references against the official current public rules page. Mark historical analyses as such where their conclusions depend on the old schedule.
2. Audit the full Git history, GitHub release assets, tracked artifacts, and proposed Pages inputs for credentials, account or personal information, licensed raw data, and research that the team does not want to disclose. `.env.local` is ignored and untracked; an initial pattern scan across 42 commits found no matches, but this is not a complete secret or privacy audit. Resolve every finding before the visibility change. Review the public disclosure of historical files, because deleting a file from the current tree does not remove it from Git history.
3. Add GitHub Actions checks for Python 3.12 dependency installation, unit tests, formatting/lint, compile/import validation, and a secret scan. Tests use mocks and local fixtures; no workflow receives AIVIX, Index One, IBKR, or competition-account credentials. PRs from forks receive no privileged write token. CI runs on pull requests and main pushes.
4. Build a static GitHub Pages site from a dedicated `site/` source directory. It includes project purpose, high-level architecture, current competition rule links, methodology summary, and explicitly labeled sanitized Paper or historical results only after those results have been independently verified. It excludes positions, live performance, exact model parameters, raw provider data, credentials, and account details. The Pages workflow deploys only after the site build and content checks pass on main.
5. After the audit and CI/Pages review, change repository visibility to public and enable Pages. Verify the public site, Actions permissions, branch protection or ruleset behavior, and that no private artifacts became accessible. The visibility change exposes the entire repository history and Actions logs, so this is the final publication step.

## Workstream B: candidate ETF strategy research and Paper validation

The first candidate is a long-only, daily-rebalanced US ETF basket: a broad US equity core, BTC/ETH-linked ETF exposure, and a short-duration Treasury ETF reserve. Exact symbols and risk weights are selected only after checking IBKR contract qualification, trading permissions, liquidity, Index One constituent support, and a frozen historical data inventory. The Hong Kong equity candidate remains available for comparison until a single competition strategy is chosen and registered.

The allocation rule keeps a separately documented minimum invested weight above the competition's 50% average-holding threshold, including when AIVIX data is unavailable. The reserve ETF's treatment in the organizer's holding-rate calculation must be confirmed; if it is excluded, the broad equity core must independently satisfy the threshold. The rule also avoids more than 10 empty trading days.

The AIVIX input is a small, predeclared set of BTC and ETH sentiment indicators, beginning with the documented CO-A sentiment family. The ingestion record stores provider identifier, indicator ID, asset, observation window, provider timestamp, retrieval timestamp, and raw-response checksum. The research process uses only observations known before a fixed US trading decision cutoff. Missing, late, revised, or ambiguous data results in a documented fallback weight and no retrospective rewrite of decisions. AIVIX credentials stay in local environment configuration and never enter Git, logs, or Pages.

The research side produces a versioned target portfolio and lineage record. A frozen daily manifest is the single source for both Index One index calculation and the existing `targets.json` handoff. Index One returns index values and weights for verification and reporting; it does not issue broker orders. The current Index One documentation has both older read-only API pages and newer workflow endpoints, so the account's actual permissions and supported ETF universe must be probed before choosing API-based creation or a browser-created index with API reads. The existing execution boundary validates targets, market semantics, risk limits, Paper environment, orders, fills, and reconciliation through IB Gateway.

Research compares (a) fixed-weight ETF basket, (b) price-only risk rule, and (c) the same basket plus AIVIX regime input on identical dates and with identical fees, spreads, rebalance timing, and data availability. The primary comparison is incremental risk-adjusted return and drawdown, with turnover, tracking error, signal coverage, and implementation shortfall reported. Historical optimization is frozen before Paper shadow. No result is described as an established alpha or as a live broker result without the corresponding evidence.

## Interfaces and implementation order

```text
AIVIX response -> timestamped research snapshot -> deterministic regime rule
IBKR historical price snapshot ----------------> daily target manifest
daily target manifest -> Index One index/weights -> comparison and audit
daily target manifest -> targets.json + lineage.json -> Paper preflight
Paper preflight -> IB Gateway Paper -> order/fill events -> reconciliation
sanitized, reviewed summary -> GitHub Pages
```

Keep ingestion, feature construction, and backtesting in the research environment. This execution repository consumes only the existing versioned handoff and adds provider-independent evidence links where necessary. Avoid importing research code by local absolute path. Build and validate the public CI/Pages boundary first; then probe provider permissions and available history; then run reproducible backtests; then run supervised Paper contract and order-lifecycle checks; then begin continuous Paper shadow. Register one strategy only after comparing it with the existing Hong Kong candidate.

## Failure handling and release gates

- AIVIX API failure or stale observation: keep the documented fallback allocation, record the failure, and do not invent a signal.
- Index One unavailable or weights disagree with the frozen manifest: stop index publication and flag a reconciliation issue; do not infer broker targets from stale index data.
- IBKR contract, quote, or account check fails: block the order and retain the target and preflight evidence. TCP reachability alone is not market-data or order verification.
- Normal runs preserve the current `environment=paper` and `dry_run=true` defaults. A supervised Paper order smoke may explicitly set `dry_run=false` after preflight and account/contract checks. A later live switch requires separate explicit controls and human supervision.
- Do not publish Pages results until their source run, period, return basis, costs, and Paper-versus-backtest status are labeled and verified.

## Acceptance criteria

1. Current rule dates and entry requirements in the repository match the official 2026-09-23 rule version, with links to the source.
2. The full-history and release-asset audit has a reviewable finding log; public visibility is changed only when all findings are resolved.
3. CI passes on a PR and main without external credentials or a live broker connection; Pages contains only reviewed, sanitized content.
4. AIVIX and Index One access is demonstrated with non-secret metadata: permitted indicators, history depth, request limits, constituent coverage, and read/write capabilities.
5. A frozen research run reproduces target weights and the three benchmark comparisons with point-in-time data and costs.
6. The Index One index's weights reconcile to the same daily manifest used by the `targets.json` handoff.
7. Supervised IB Gateway Paper tests cover contract qualification, submit/cancel/fill events, restart recovery, and reconciliation before continuous shadow is called operational.

## Sources checked

- Competition overview and rules: https://fundconnecthk.com/quant-league/ and https://fundconnecthk.com/quant-league/legal/competition-rules/
- Cryptoracle indicator catalog and API guide: https://cryptoracle.gitbook.io/cryptoracle-docs/co-indicator-repository and https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1/previous-versions/cryptoracle-open-api-v1.2/quick-start-guide
- Index One API and execution engine: https://indexone.io/docs/api and https://indexone.io/docs/reference/execution-engine
- GitHub repository visibility and Pages behavior: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility and https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages
