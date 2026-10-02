# International target manifest v2

The independent `TargetManifestV2` is an interchange contract for ETF, equity and futures targets. It is not executable by the current runner. Research and run-lineage ownership remains with the research system.

## Complete synthetic example

These identifiers and quantities are synthetic and must not be treated as qualified contracts or trading recommendations.

```json
{
  "schema_version": "2.0",
  "strategy_id": "synthetic-international",
  "as_of": "2026-10-02T08:00:00Z",
  "reporting_currency": "USD",
  "targets": [
    {
      "instrument": {
        "asset_type": "etf",
        "symbol": "ETF_TEST",
        "market": "US",
        "exchange_mic": "XNYS",
        "currency": "USD"
      },
      "weight": "0.30"
    },
    {
      "instrument": {
        "asset_type": "equity",
        "symbol": "EQUITY_TEST",
        "market": "JP",
        "exchange_mic": "XTKS",
        "currency": "JPY"
      },
      "weight": "0.20",
      "quantity": "100"
    },
    {
      "instrument": {
        "asset_type": "future",
        "symbol": "FUT_TEST",
        "market": "US",
        "exchange_mic": "XCME",
        "currency": "USD",
        "contract_month": "202612",
        "expiry_date": "2026-12-18",
        "multiplier": "50",
        "tick_size": "0.25",
        "roll_rule_id": "synthetic-roll.v1",
        "settlement_type": "cash",
        "margin_model_id": "synthetic-margin.v1"
      },
      "weight": "0.10",
      "quantity": "2"
    }
  ]
}
```

## Explicit parsing

```python
import json
from pathlib import Path
from packages.contracts import TargetManifestV2

payload = json.loads(Path("targets.v2.json").read_text(encoding="utf-8"))
manifest = TargetManifestV2.from_dict(payload)
serialized = manifest.to_dict()
```

Use `from_dict` at every untrusted input boundary. The frozen dataclasses are typed records, not independently validating direct constructors. Decimal fields remain plain strings on the wire; numbers, scientific notation, nonfinite values and negative values are rejected. Weights range from zero to one and their exact aggregate must not exceed one. Security quantities may be absent; present quantities are positive. Futures require positive integral contract counts. Shorts, signed net exposure and a weight-to-quantity sizing policy are outside this contract.

`as_of` is UTC with `Z` or `+00:00`; fractional seconds have at most six digits. Serialization uses `Z` and preserves microseconds without truncation. Naive/local timestamps and finer precision are rejected. Text identifiers are stripped of surrounding whitespace during parsing.

## Instrument identity and semantics

Every target specifies its own asset type, symbol, market, MIC and quote currency. There is no root market. Security identity is `(asset_type, market, exchange_mic, symbol)`; futures add contract month. Repeated identity is rejected even if metadata differs. Different futures months are distinct contracts.

MIC, currency and market checks validate syntax only. A MIC is not an IBKR routing exchange; a later adapter must explicitly qualify the contract, verify routing and currency, and check permissions. A valid currency pattern does not establish ISO assignment or account support.

Futures metadata includes contract month, expiry, multiplier, tick size, settlement type, roll-rule ID and margin-model ID. Expiry must be later than the as-of UTC date: same-date expiry is conservatively rejected because exchange expiry times and sessions are not represented. The roll and margin IDs are provenance references; they do not implement rolling or broker margin calculations. Weight is not a substitute for futures notional, margin or risk validation.

## JSON Schema versus Python

`schemas/targets.v2.schema.json` is separate from the unchanged v1 schema. It checks wire shapes, decimal strings and instrument variants. Always also use the Python parser for exact aggregate weight, compound identity uniqueness and expiry relative to as-of.

When validating JSON Schema, use the test extras (`jsonschema[format-nongpl]`) and explicitly enable the date formats:

```python
from jsonschema import Draft202012Validator, FormatChecker
validator = Draft202012Validator(schema, format_checker=FormatChecker(formats=["date", "date-time"]))
validator.validate(payload)
```

Format support requires its optional dependencies; see the [official format-validation documentation](https://python-jsonschema.readthedocs.io/en/stable/validate/#validating-formats).

## Execution compatibility

`TargetSet.from_dict`, the Nira handoff and current preflight remain v1-only. `ExecutionRunner.run` and `run_rebalance` reject v2, duck-typed substitutes and non-v1 `TargetSet` objects before broker calls or journal writes, including dry-run mode. No automatic dispatch, metadata-dropping conversion or v2 broker integration is provided.

Before international execution, add explicit account/venue routing, contract qualification, capital and FX sizing, lot/tick checks, futures margin and expiry controls, market permissions and supervised Paper lifecycle validation.
