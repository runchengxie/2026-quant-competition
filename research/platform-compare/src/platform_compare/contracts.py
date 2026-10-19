"""Strict competition input mapping; accounting remains owned by quant-platform."""

import hashlib
import json
from pathlib import PurePosixPath
import re
from datetime import datetime, timedelta
from decimal import Decimal

PIN = "28a32ba707ad72d1eb68cde5075663e1b3819ac7"
PROVIDER = {"repository": "quant-platform", "commit": PIN}


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def fields(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise ValueError("INVALID_FIELDS")
    return value


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("DUPLICATE_KEY")
            result[key] = value
        return result

    def reject(value):
        raise ValueError("INVALID_JSON_NUMBER")

    return json.loads(
        path.read_text(encoding="utf-8-sig"),
        object_pairs_hook=unique,
        parse_constant=reject,
        parse_float=reject,
    )


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("INVALID_TEXT")
    return value


def sha(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("INVALID_DIGEST")
    return value


def money(value):
    if (
        not isinstance(value, str)
        or re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value) is None
    ):
        raise ValueError("INVALID_DECIMAL")
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("INVALID_DECIMAL")
    return result


def timestamp(value):
    if (
        not isinstance(value, str)
        or re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)",
            value,
        )
        is None
    ):
        raise ValueError("INVALID_UTC_TIMESTAMP")
    return datetime.fromisoformat(value)


def count(value):
    if type(value) is not int or value <= 0:
        raise ValueError("INVALID_COUNT")
    return value


def clock(value):
    from research_contracts import ResearchClock

    fields(
        value,
        "schema_version timezone information_cutoff_at signal_at decision_at valuation_at timing_policy_id trading_calendar_ref earliest_order_at execution_window_start_at execution_window_end_at",
    )
    if value["timezone"] != "UTC":
        raise ValueError("INVALID_CLOCK_TIMEZONE")
    for key, item in value.items():
        if key.endswith("_at") and item is not None:
            timestamp(item)
    return ResearchClock.from_mapping(value)


def load_request(path, dataset_root):
    request = fields(
        read_json(path),
        "schema_version provider run_id market synthetic evidence input_ref input_fingerprint config config_fingerprint",
    )
    if (
        request["schema_version"] != "competition.accounting_request.v1"
        or request["provider"] != PROVIDER
    ):
        raise ValueError("UNSUPPORTED_PROVIDER_OR_SCHEMA")
    if (
        request["market"] not in ("HK", "US")
        or type(request["synthetic"]) is not bool
        or request["evidence"] != "software_diagnostic"
    ):
        raise ValueError("INVALID_EVIDENCE")
    if request["synthetic"] is not True:
        # This version has no independent real-input provenance/timing adapter.
        # Matching caller booleans cannot certify synthetic fixtures as real data.
        raise ValueError("REAL_INPUT_EVIDENCE_UNVERIFIED")
    if (
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", text(request["run_id"]))
        is None
    ):
        raise ValueError("INVALID_RUN_ID")
    config = fields(
        request["config"],
        "initial_cash sizing_mode commission_bps slippage_bps fx_cost_bps max_price_age_seconds max_fx_age_seconds fx_pairs allow_assumed_availability return_basis allow_modeled_execution_prices",
    )
    if sha(request["config_fingerprint"]) != digest(config):
        raise ValueError("CONFIG_MISMATCH")
    ref = fields(request["input_ref"], "artifact_id relative_path sha256 size_bytes")
    text(ref["artifact_id"])
    name = text(ref["relative_path"])
    relative = PurePosixPath(name)
    if (
        not relative.parts
        or relative.is_absolute()
        or relative.as_posix() != name
        or ".." in relative.parts
        or "\\" in name
        or ":" in name
    ):
        raise ValueError("UNSAFE_INPUT_REFERENCE")
    root = dataset_root.resolve(strict=True)
    source = (root / name).resolve(strict=True)
    if not root.is_dir() or not source.is_file() or not source.is_relative_to(root):
        raise ValueError("UNSAFE_INPUT_REFERENCE")
    if type(ref["size_bytes"]) is not int or ref["size_bytes"] < 0:
        raise ValueError("INVALID_SIZE")
    if sha(request["input_fingerprint"]) != sha(ref["sha256"]):
        raise ValueError("INPUT_MISMATCH")
    check_source(source, ref)
    asset = fields(
        read_json(source),
        "schema_version market synthetic upstream_input_fingerprint instruments prices fx decisions valuation_times research_clock",
    )
    if (
        asset["schema_version"] != "competition.accounting_inputs.v1"
        or type(asset["synthetic"]) is not bool
        or asset["synthetic"] != request["synthetic"]
        or asset["market"] != request["market"]
    ):
        raise ValueError("INPUT_METADATA_MISMATCH")
    sha(asset["upstream_input_fingerprint"])
    for key in ("instruments", "prices", "fx", "decisions", "valuation_times"):
        if not isinstance(asset[key], list):
            raise ValueError("INVALID_RECORD_LIST")
    return request, asset, source


def check_source(path, ref):
    if (
        path.stat().st_size != ref["size_bytes"]
        or hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]
    ):
        raise ValueError("INPUT_BYTES_CHANGED")


def owner_request(request, asset):
    from research_contracts import ArtifactRef
    from portfolio_backtester.usd_ledger_models import (
        USDInstrument,
        USDPriceObservation,
        USDFXObservation,
        USDRebalanceDecision,
        USDReplayConfig,
        USDReplayRequest,
    )

    ref = ArtifactRef(
        request["input_ref"]["artifact_id"], request["input_ref"]["sha256"]
    )
    instruments = []
    for item in asset["instruments"]:
        fields(item, "instrument_id asset_type currency lot_size session_policy_id")
        if not text(item["instrument_id"]).startswith(request["market"] + "."):
            raise ValueError("INSTRUMENT_MARKET_MISMATCH")
        count(item["lot_size"])
        instruments.append(USDInstrument(**item))
    prices = []
    for item in asset["prices"]:
        fields(
            item,
            "instrument_id price_at available_at price unit availability_basis session_policy_id execution_eligible",
        )
        if type(item["execution_eligible"]) is not bool:
            raise ValueError("INVALID_ELIGIBILITY")
        prices.append(
            USDPriceObservation(
                **(
                    item
                    | {
                        "price_at": timestamp(item["price_at"]),
                        "available_at": timestamp(item["available_at"]),
                        "price": money(item["price"]),
                        "source_ref": ref,
                    }
                )
            )
        )
    fx = []
    for item in asset["fx"]:
        fields(
            item,
            "base_currency quote_currency price_at available_at rate unit availability_basis",
        )
        fx.append(
            USDFXObservation(
                **(
                    item
                    | {
                        "price_at": timestamp(item["price_at"]),
                        "available_at": timestamp(item["available_at"]),
                        "rate": money(item["rate"]),
                        "source_ref": ref,
                    }
                )
            )
        )
    decisions = []
    for item in asset["decisions"]:
        fields(item, "decision_id clock weights execution_times")
        if not isinstance(item["weights"], dict) or not isinstance(
            item["execution_times"], dict
        ):
            raise ValueError("INVALID_DECISION")
        decisions.append(
            USDRebalanceDecision(
                text(item["decision_id"]),
                clock(item["clock"]),
                {text(key): money(value) for key, value in item["weights"].items()},
                {
                    text(key): timestamp(value)
                    for key, value in item["execution_times"].items()
                },
            )
        )
    config = request["config"]
    converted = dict(config)
    for key in ("initial_cash", "commission_bps", "slippage_bps", "fx_cost_bps"):
        converted[key] = money(config[key])
    for name in ("price", "fx"):
        converted["max_" + name + "_age"] = timedelta(
            seconds=count(converted.pop("max_" + name + "_age_seconds"))
        )
    if not isinstance(config["fx_pairs"], dict) or any(
        not isinstance(pair, list)
        or len(pair) != 2
        or not all(isinstance(p, str) for p in pair)
        for pair in config["fx_pairs"].values()
    ):
        raise ValueError("INVALID_FX_PAIRS")
    converted["fx_pairs"] = {
        key: tuple(pair) for key, pair in config["fx_pairs"].items()
    }
    return USDReplayRequest(
        tuple(instruments),
        tuple(prices),
        tuple(fx),
        tuple(decisions),
        tuple(timestamp(value) for value in asset["valuation_times"]),
        USDReplayConfig(**converted),
    )
