# Offline research

[简体中文](README.zh-CN.md)

Use the [team quickstart](../docs/operations/team-quickstart.md) for isolated setup and synthetic demos from one checkout. Default delivery does not install quant framework packages; accounting comparison remains optional.


[International offline experiments](../docs/research/international-experiments.md)

- [Crypto market-making](crypto-mm/README.md): event-driven visible-queue simulation and synthetic Parquet fixtures.
- [Equity lab](equity-lab/README.md): daily CSV/YAML fractional-weight backtests and fictional HK-symbol fixtures.

Each directory is an independent Python 3.12 project with its own `uv.lock`, tests and MIT license. Install and run checks from that directory. Root execution dependencies and tests remain separate; root Ruff covers the new files. English is canonical; reader documentation is also available in zh-CN. No runtime locale system is implemented.

Generated data and reports belong under the configured external `DATA_ROOT/2026-quant-competition/research/` owner directory. None of these packages connects to a broker. Their artifacts are not executable target handoffs. The published v1 JSON schema accepts JP/US, while runtime market normalization also recognizes HK. This existing mismatch remains unresolved; crypto is unsupported. Competition eligibility and live-market validity require separate checks. See each package's limitations before interpreting results.

MIT applies only to the new subproject code. This addition does not license existing root code or third-party dependencies.

## Input and experiment acceptance

The opt-in [research acceptance tools](../docs/research/research-acceptance.md) inspect explicit manifests and issue input receipts. These new entry points do not require global data configuration. Successful software checks do not establish research eligibility; owner provenance and holdout protocol validation remain unavailable. Default strategies and existing reports are preserved.

## Optional accounting comparison

The independent [accounting package](platform-compare/README.md) includes a competition-owned cash/share ledger without external framework dependencies. It supports accounting comparisons and five-market next-open diagnostics. The [comparison guide](../docs/research/accounting-comparison.md) explains model differences and real-input limitations.
