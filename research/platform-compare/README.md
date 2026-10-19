# Fixed-version accounting adapter

[简体中文](README.zh-CN.md)

This independent offline package maps explicit HK/US replay inputs to the public `quant-platform` USD price ledger. It produces diagnostic software evidence only. It does not replace the project's existing backtest engines, certify research, publish results or connect to a broker.

Both `quant-platform` and `research-contracts` are installed from public Git revision `28a32ba707ad72d1eb68cde5075663e1b3819ac7`. Runtime distribution metadata must confirm that revision and repository. A sibling source checkout is not an installation fallback. The independent lock keeps the provider's dependencies separate from the root, equity and crypto environments.

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

The strict `competition.accounting_request.v1` request has exact fields `schema_version`, `provider`, `run_id`, `market`, `synthetic`, `evidence`, `input_ref`, `input_fingerprint`, `config`, `config_fingerprint`. `provider` is the fixed repository/commit identity; `market` is `HK` or `US`; `synthetic` must be `true` in this version; `evidence` is `software_diagnostic`.

`input_ref` contains `artifact_id`, a canonical relative `relative_path`, SHA256 `sha256` and integer `size_bytes`. Its hash must equal `input_fingerprint`. Referenced bytes are resolved within the explicit dataset root and checked before and after replay. This binds the input asset, not a vendor provenance guarantee.

That separate `competition.accounting_inputs.v1` JSON asset contains exact fields `schema_version`, `market`, `synthetic`, `upstream_input_fingerprint`, `instruments`, `prices`, `fx`, `decisions`, `valuation_times`, `research_clock`. Price and FX observations are loaded only from these hashed bytes. The adapter supplies owner `ArtifactRef` values from the asset's verified reference. It does not duplicate unbound observations in the request.

Financial values are finite decimal strings. JSON floats, booleans used as counts, duplicate keys, unknown fields and unsupported units are rejected. Times must be explicit UTC with at most microsecond precision, matching the owner Python datetime contract. Finer precision is rejected rather than truncated. Research clocks, availability, execution eligibility and session policy remain explicit owner inputs. This version accepts synthetic inputs only. Requests with `synthetic=false` fail with `REAL_INPUT_EVIDENCE_UNVERIFIED`, even if their clocks and hashes are internally consistent. Real inputs require a separate independently checked source and timing evidence adapter; changing a caller flag cannot provide that evidence.

`config` contains exact owner-facing fields `initial_cash`, `sizing_mode`, `commission_bps`, `slippage_bps`, `fx_cost_bps`, `max_price_age_seconds`, `max_fx_age_seconds`, `fx_pairs`, `allow_assumed_availability`, `return_basis`, `allow_modeled_execution_prices`. Its fingerprint is SHA256 of UTF-8 JSON with sorted keys, compact separators, `ensure_ascii=false` and no nonfinite numbers. The same canonical digest is used for the exported schedule identity. See [contracts.py](src/platform_compare/contracts.py) for exact record fields.

The provider performs settlement, cash/share valuation, cost and FX accounting, lot rounding and independent bundle reconciliation. Its publisher creates the owner manifest, Parquet inventory and diagnostics. Verification uses the actual owner reader with hashes enabled and checks the request, input reference, config, clock, backend and diagnostic tier. Verification also replays the complete request through the public owner APIs and publisher in a temporary external directory, then compares all diagnostics. This rejects mutable manifest relabeling as well as changed tables and substituted requests. Temporary replay files are removed afterward. No loose `comparison.json` sidecar is trusted.

`competition.accounting_result.v1` is an aggregate projection derived from that verified inventory. It includes provider/input/config/schedule/manifest fingerprints, decimal USD cash/NAV/position/cost/notional values, sizing and cost assumptions, counts, `orders_submitted=false` and `order_lifecycle=false`. A new process can regenerate it using `verify`. It is diagnostic, not `accepted_research` or proof of broker execution. Cash/share drift can differ from lagged weight proxies; numerical parity is not promised.

## Tests and boundaries

```powershell
& $comparisonPython -m pytest research/platform-compare/tests -q
```

Tests run actual pinned owner replay, publication and verification on synthetic all-cash, US holdings, costs, HK heterogeneous lots and FX inputs. They cover invalid units, stale/future observations, changed bytes, request substitution, table mutation and safe CLI errors. No licensed market data, account or network broker call is needed. New adapter code is MIT; dependencies retain their licenses.
