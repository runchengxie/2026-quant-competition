# Standalone accounting and comparison experiments

[简体中文](README.zh-CN.md)

This standalone offline package owns a USD price ledger for HK/US accounting comparisons and five-market next-open diagnostics. It installs neither `quant-platform` nor `research-contracts` and needs no sibling checkout. Results do not certify research or connect to brokers.

The ledger is derived from public revision `28a32ba707ad72d1eb68cde5075663e1b3819ac7`, relocated to `platform_compare.accounting`, with Apache-2.0 licensing, source inventory and file hashes retained. Adapters remain MIT. See [source provenance](src/platform_compare/accounting/ORIGIN.json). This revision describes ancestry, not an external runtime provider. A separate lock still isolates research dependencies.

Use Python 3.12 and an external environment:

```powershell
$env:UV_PROJECT_ENVIRONMENT = $comparisonEnvironment
uv sync --locked --group dev --project research/platform-compare
& $comparisonPython -m platform_compare.cli --help
& $comparisonPython -m platform_compare.cli run --request $requestJson --dataset-root $datasetRoot --output $newBundleDirectory
& $comparisonPython -m platform_compare.cli verify --request $requestJson --dataset-root $datasetRoot --bundle $newBundleDirectory
```

All inputs, environments and output bundles belong outside source under resolved `DATA_ROOT/2026-quant-competition/`. The output directory must not already exist. Current session-date-only historical CSV files cannot supply the explicit causal clocks required here. Do not infer availability, execution times, FX or lot sizes from their names or dates.

## Input and output contract

The strict `competition.accounting_request.v2` request has exact fields `schema_version`, `provider`, `run_id`, `market`, `synthetic`, `evidence`, `input_ref`, `input_fingerprint`, `config`, `config_fingerprint`. `provider` is `{repository: "2026-quant-competition", engine: "competition.usd_price_ledger", version: "1"}`; `market` is `HK` or `US`; `synthetic` must be `true` in this version; `evidence` is `software_diagnostic`.

`input_ref` contains `artifact_id`, a canonical relative `relative_path`, SHA256 `sha256` and integer `size_bytes`. Its hash must equal `input_fingerprint`. Referenced bytes are resolved within the explicit dataset root and checked before and after replay. This binds the input asset, not a vendor provenance guarantee.

That separate `competition.accounting_inputs.v1` JSON asset contains exact fields `schema_version`, `market`, `synthetic`, `upstream_input_fingerprint`, `instruments`, `prices`, `fx`, `decisions`, `valuation_times`, `research_clock`. Price and FX observations are loaded only from these hashed bytes. The adapter supplies owner `ArtifactRef` values from the asset's verified reference. It does not duplicate unbound observations in the request.

Financial values are finite decimal strings. JSON floats, booleans used as counts, duplicate keys, unknown fields and unsupported units are rejected. Times must be explicit UTC with at most microsecond precision, matching the owner Python datetime contract. Finer precision is rejected rather than truncated. Research clocks, availability, execution eligibility and session policy remain explicit owner inputs. This version accepts synthetic inputs only. Requests with `synthetic=false` fail with `REAL_INPUT_EVIDENCE_UNVERIFIED`, even if their clocks and hashes are internally consistent. Real inputs require a separate independently checked source and timing evidence adapter; changing a caller flag cannot provide that evidence.

`config` contains exact owner-facing fields `initial_cash`, `sizing_mode`, `commission_bps`, `slippage_bps`, `fx_cost_bps`, `max_price_age_seconds`, `max_fx_age_seconds`, `fx_pairs`, `allow_assumed_availability`, `return_basis`, `allow_modeled_execution_prices`. Its fingerprint is SHA256 of UTF-8 JSON with sorted keys, compact separators, `ensure_ascii=false` and no nonfinite numbers. The same canonical digest is used for the exported schedule identity. See [contracts.py](src/platform_compare/contracts.py) for exact record fields.

The provider performs settlement, cash/share valuation, cost and FX accounting, lot rounding and independent bundle reconciliation. Its publisher creates the owner manifest, Parquet inventory and diagnostics. Verification uses the actual owner reader with hashes enabled and checks the request, input reference, config, clock, backend and diagnostic tier. Verification also replays the complete request through the local ledger APIs and publisher in a temporary external directory, then compares all diagnostics. This rejects mutable manifest relabeling as well as changed tables and substituted requests. Temporary replay files are removed afterward. No loose `comparison.json` sidecar is trusted.

`competition.accounting_result.v2` is an aggregate projection derived from that verified inventory. It includes provider/input/config/schedule/manifest fingerprints, decimal USD cash/NAV/position/cost/notional values, sizing and cost assumptions, counts, `orders_submitted=false` and `order_lifecycle=false`. A new process can regenerate it using `verify`. It is diagnostic, not `accepted_research` or proof of broker execution. Cash/share drift can differ from lagged weight proxies; numerical parity is not promised.

## Tests and boundaries

```powershell
& $comparisonPython -m pytest research/platform-compare/tests -q
```

Tests run actual local-engine replay, publication and verification on synthetic all-cash, US holdings, costs, HK heterogeneous lots and FX inputs. They cover invalid units, stale/future observations, changed bytes, request substitution, table mutation and safe CLI errors. No licensed market data, account or network broker call is needed. Adapters are MIT; derived accounting code and tests retain Apache-2.0.

## Historical compatibility

New requests and result projections use v2. Historical fixed-provider v1 artifacts remain unchanged and must not be relabeled. Five-market locks use `global_etf_next_open.input_lock.v2` with `accounting_engine` instead of `platform_revision`. Existing CLI/module paths and `setup --profile framework` remain compatible; this profile now installs only the local accounting package.
