# Research input and experiment acceptance

[简体中文](research-acceptance.zh-CN.md)

The opt-in acceptance tools check file identity, input quality and experiment structure. They preserve existing strategies, default engines and reports. A successful backtest process alone does not establish usable research evidence. These tools neither connect to a broker nor produce execution targets.

## What is available

1. Each independently installed research package inspects an explicit input manifest and emits `competition.research_input_receipt.v1`.
2. The root consumer validates that receipt and rehashes the exact source bytes beneath an explicit dataset root.
3. The experiment gate checks supplied configuration, summary and observations. It can return `accepted_diagnostic` or `blocked`.

Owner provenance and holdout protocol validation are not integrated. Every `research_evidence` request therefore remains `blocked` with `OWNER_CONTRACT_VALIDATION_UNAVAILABLE`. No `verified` boolean or positive return can enable `accepted_research` in this version. Synthetic inputs, unknown provenance and previously exposed histories remain explicitly identified.

## Input manifest

Keep the manifest and receipt outside Git. The dataset root must be an existing absolute directory. File references use canonical `/`-separated relative paths. Absolute references, `..`, duplicate references, symlink escapes, changed hashes and size mismatches are rejected. Inspection hashes files before and after reading and does not rewrite their bytes. This is change detection, not an atomic filesystem snapshot. Recheck at consumption time.

Here is the complete equity manifest shape. Replace the root, hash and size with actual values. `unknown` is a value, not a request to infer missing provenance.

```json
{
  "schema_version": "competition.research_input_manifest.v1",
  "dataset_root": "/absolute/external/market-data",
  "producer": {
    "package": "competition-equity-lab",
    "package_version": "0.1.0",
    "code_revision": "unknown"
  },
  "dataset_id": "study-input-v1",
  "market": "HK",
  "synthetic": false,
  "source_state": "archived_unverified",
  "timezone": "Asia/Hong_Kong",
  "price_basis": "unknown",
  "universe_state": "fixed_current",
  "availability_state": "unknown",
  "files": [
    {
      "relative_path": "HK_TEST.csv",
      "kind": "daily_bars",
      "sha256": "<64 lowercase hex characters from the exact file bytes>",
      "size_bytes": 1234
    }
  ]
}
```

| Field | Allowed values |
| --- | --- |
| `market` | `HK`, `US`, `CRYPTO` |
| `source_state` | `synthetic`, `archived_unverified`, `owner_published` |
| `price_basis` | `raw`, `adjusted`, `unknown` |
| `universe_state` | `synthetic`, `fixed_current`, `point_in_time`, `unknown` |
| `availability_state` | `verified`, `period_only`, `unknown` |
| `timezone` | IANA timezone name or `unknown` |
| `kind` | `daily_bars`, `orderbook`, `trades`, `fundings` |

`synthetic` must agree with both synthetic metadata fields. A claimed `owner_published` or `verified` value is not independent attestation. `code_revision` is 40 lowercase hex characters or `unknown`. The current producers require their package name and version `0.1.0`. The root receipt schema is [input-receipt.v1.schema.json](../../schemas/research/input-receipt.v1.schema.json); the Python consumer also enforces fingerprints, paths and metadata consistency.

Equity supports HK/US daily CSVs with `date,open,high,low,close,volume,code`. Dates must use `YYYY-MM-DD`, and symbols must match the declared market. It rejects boolean OHLCV values, nonfinite/nonpositive prices, invalid OHLC bounds, negative/missing volume and duplicate date/code observations across files. Inspection does not forward-fill or certify adjustments, corporate actions, exchange calendars, universe completeness or point-in-time availability.

Crypto uses `competition-crypto-mm` and `market=CRYPTO`. It requires all three groups, matching daily date coverage, `datetime` stored as nanosecond Parquet datetimes, and the existing book/trade/funding audit rules. Timezone-aware columns must match the declared timezone. Naive timestamps can retain `unknown`; assigning a timezone in the manifest does not prove their origin. Files are named `YYYY-MM-DD.parquet`. Empty files and nonzero quality counts are rejected. This does not establish venue/product identity or exchange fill realism. No L3 order identities are fabricated.

The receipt excludes `dataset_root`, adds per-file `rows`, `quality.issue_codes` and `fingerprint`, and preserves file-list order. Its fingerprint is SHA-256 of UTF-8 canonical JSON excluding `fingerprint`, with sorted keys, compact separators, Unicode preserved and nonfinite numbers forbidden. File SHA-256 values always cover exact bytes, including LF/CRLF differences.

## Commands and exit codes

Install each package in its own Python 3.12 environment using its committed lockfile. Keep `UV_PROJECT_ENVIRONMENT` outside the checkout. For these new commands, explicit manifests replace global data configuration; `--help` works without data, private settings or broker modules. Other legacy commands retain their documented configuration requirements.

Run the appropriate producer from its research directory:

```sh
uv run --locked python -m equity_lab.validation --manifest <manifest.json> --output <receipt.json>
uv run --locked python -m crypto_mm.commands.validate_inputs --manifest <manifest.json> --output <receipt.json>
```

Then use the root environment:

```sh
uv run --locked python -m competition_tools.research_acceptance --receipt <receipt.json> --dataset-root <absolute-data-root>
uv run --locked python -m competition_tools.experiment_acceptance --plan <plan.json> --input-receipt <receipt.json> --summary <summary.json> --observations <positions.csv-or-events.json> --dataset-root <absolute-data-root> --output <acceptance.json>
```

Angle-bracket arguments are placeholders. Producers exit 0 after successful software inspection and receipt creation. The root input consumer exits 0 with `diagnostic_only` when structural/file/quality checks succeed, even if provenance warnings remain. The experiment gate exits 0 only for an accepted requested purpose. It exits 2 for `blocked` or invalid evidence. Errors use stable codes and omit raw private paths, including argument-parser failures (`INVALID_ARGUMENTS`). Output creation is exclusive; choose a new filename instead of overwriting evidence.

## Experiment plan and observations

`competition.experiment_plan.v1` requires exactly these keys:

| Keys | Contract |
| --- | --- |
| `purpose`, `evaluation_kind` | `software_diagnostic` or `research_evidence`; `retrospective` or `owner_unexposed` |
| `strategy_id`, `config` | Stable strategy identifier and the supplied configuration object |
| `config_fingerprint`, `input_fingerprint`, `output_fingerprint` | Canonical config digest, input receipt fingerprint, canonical digest of `{"summary": summary, "observations": observations}` |
| `sample_interval` | Inclusive `start` and `end` ISO dates/datetimes |
| `windows` | `training`, `validation`, `evaluation`; each is an inclusive start/end object or null, except evaluation is required |
| `minimum_universe`, `minimum_observations` | Positive integers; evaluation instrument count and distinct evaluation timestamps |
| `costs` | `fee_bps`, `slippage_bps`, `currency`, `verified`; finite fees, nonnegative slippage, explicit boolean |
| `history_exposed`, `owner_protocol_receipt` | Boolean exposure declaration and optional owner reference object, never an approval |

Timestamps retain up to nine fractional digits with exact nanosecond comparisons and offset-equivalent identity. Finer precision is rejected. Dates use `YYYY-MM-DD`; datetimes add `T` or a space, `HH:MM:SS`, an optional fractional part and optional `Z` or `±HH:MM`. Use consistent timezone awareness. All windows must lie inside the sample interval. Overlapping windows block acceptance. Previously visible history cannot be claimed as an untouched evaluation. A software diagnostic can retain explicit in-sample/provenance warnings; it is not out-of-sample evidence.

The gate accepts existing equity `summary.json` and `positions_daily.csv`, recognizing `strategy`, `run_status`, `fallback_reasons`, `target_weight` and `cnn_walk_forward_fold`. CSV contract columns `target_weight`, `inventory` and nonempty fold values are parsed as numbers before output fingerprinting. JSON observations must already contain numeric values. Use the tool's `canonical_digest` for the same representation. Original report bytes and metrics are not rewritten. Missing positions, missing required folds, fallbacks, duplicate observations and insufficient evaluation coverage block acceptance. Known non-walk-forward image models retain `IN_SAMPLE_MODEL`. Counted folds require complete retained training/validation/test intervals, disjoint ordering, containment in declared windows and consistency across observations. Positive declared `cnn_purge_days` or `cnn_embargo_days` remain blocked with `FOLD_PURGE_UNVERIFIED`: partial evaluation rows cannot verify trading-observation and label gaps. Calendar days are not substituted. Legacy equity configuration metadata contains path labels, not run configuration bytes; `CONFIG_BINDING_UNVERIFIED` records that limitation without following private paths.

Crypto compares structured `summary.config` to `plan.config` and its maker fee to `costs.fee_bps`; explicit contradictions block acceptance. Missing structured run config also blocks crypto acceptance. Crypto requires JSON event observations with `datetime` and finite `inventory`, plus finite summary metrics `total_pnl`, `fee_cashflow`, `max_absolute_inventory` and integral `fill_count`. `pnl_unit` must explicitly name `HKD`, `USD`, `USDT`, `USDC` or `quote_currency`. Percentage return requires positive `funded_capital`. Unknown cost currency or unverified fees blocks research evidence. This gate checks supplied consistency, not an independent recomputation of a backtest, the fee ledger or owner-governed folds.

The retained output uses `competition.experiment_acceptance.v1`: status, purpose, sorted stable issue codes, three fingerprints and sample counts. `public_acceptance_summary` rejects unknown fields and permits only this aggregate contract. It is a validation helper for a separately reviewed publication step. These commands never publish receipts, raw data, filenames or provider responses to Pages.

## Verification and remaining work

The synthetic cross-environment check runs an actual leaf producer and then the root consumer:

```sh
uv run --locked python -m competition_tools.check_research_receipts --project equity-lab --leaf-python <equity-environment-python> --output-root <new-external-directory>
uv run --locked python -m competition_tools.check_research_receipts --project crypto-mm --leaf-python <crypto-environment-python> --output-root <another-new-external-directory>
```

CI executes both with separate locked environments. Neither installs private research owners. Tests cover byte changes, unsafe paths, metadata, input boundaries, fallback/empty/overlap cases, fingerprints, CLI errors and aggregate privacy. Existing Pages locale tests compare machine facts across English and Chinese.

Applying the new gate to retained 2026-10-19 reports blocked all 16 leaf equity runs as research evidence. HK remains one stock and US remains SPY only. Zero-position CNN and no-fold runs have explicit additional blockers. All four archived crypto aggregate reports also remain blocked, including missing retained per-event observations and declared PnL units. The four root monthly/proxy reports lack this adapter's compatible retained position/source receipts and were not assessed. No historical backtest was rerun for this gate check. The [24-result snapshot](strategy-validation-2026-10-19.md) remains unchanged.

Future accounting adapters should reuse fixed owner APIs through versioned artifacts or separate environments. `quant-platform` accounting/contracts are not installed by this addition. Read-only local verification found its default IBKR factory's `quant_execution_engine.broker.ibkr` import unavailable; that finding does not describe this repository's separate IBKR adapter. `quant-backtest-runtime` currently requires Linux and is not enabled on Windows. Model/research/reporting owners with incompatible pandas or module namespaces remain separate processes. Data provenance, causal FX, corporate actions, a complete study universe, owner holdout governance and the supervised Paper lifecycle remain follow-up work. See [architecture](../../ARCHITECTURE.md).
