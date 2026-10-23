"""Hash-bound input evidence; no broker or sibling project imports."""

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..next_open.calendar import CALENDAR_PACKAGE_VERSION
from ..owner_adapter import external_output

# A real action-coverage review must be inspected and committed before use.
TRUSTED_ACTION_REVIEWS: frozenset[str] = frozenset()


@dataclass(frozen=True)
class USNextSessionInputs:
    schedule: dict
    assets: dict[str, pd.DataFrame]
    action_evidence: dict
    input_hashes: dict[str, str]


def _read(path):
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_INPUT")),
    )


def _bound_file(record):
    if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
        raise ValueError("INVALID_FILE_RECEIPT")
    path = external_output(Path(record["path"]))
    if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("INPUT_HASH_CHANGED")
    return path


def load_us_inputs(spec_path: Path) -> USNextSessionInputs:
    path = external_output(spec_path)
    spec = _read(path)
    keys = {
        "schema",
        "synthetic",
        "calendar",
        "signal_basis",
        "execution_basis",
        "quote_currency",
        "sizing_mode",
        "instruments",
        "files",
        "actions",
        "schedule",
    }
    if (
        not isinstance(spec, dict)
        or set(spec) != keys
        or spec["schema"] != "competition.us_next_session_inputs.v1"
        or type(spec["synthetic"]) is not bool
    ):
        raise ValueError("INVALID_US_INPUT_SPEC")
    if spec["signal_basis"] != "raw" or spec["execution_basis"] != "raw":
        raise ValueError("RAW_SIGNAL_EXECUTION_BASIS_REQUIRED")
    if spec["quote_currency"] != "USD" or spec["sizing_mode"] not in {
        "fractional",
        "integral",
    }:
        raise ValueError("UNSUPPORTED_CURRENCY_OR_SIZING")
    if spec["calendar"] != dict(
        name="XNYS", package="exchange_calendars", version=CALENDAR_PACKAGE_VERSION
    ):
        raise ValueError("CALENDAR_EVIDENCE_UNVERIFIED")
    if (
        not isinstance(spec["instruments"], dict)
        or not spec["instruments"]
        or set(spec["instruments"]) != set(spec["files"])
    ):
        raise ValueError("INSTRUMENT_FILE_MISMATCH")
    hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()}
    assets = {}
    for instrument, metadata in spec["instruments"].items():
        if (
            not isinstance(instrument, str)
            or not instrument
            or set(metadata) != {"currency", "lot_size"}
            or metadata["currency"] != "USD"
            or type(metadata["lot_size"]) is not int
            or metadata["lot_size"] < 1
        ):
            raise ValueError("INSTRUMENT_LOT_OR_CURRENCY_UNVERIFIED")
        source = _bound_file(spec["files"][instrument])
        frame = pd.read_csv(source)
        if set(frame.columns) != {"date", "open", "close"} or frame.empty:
            raise ValueError("INVALID_PRICE_COLUMNS")
        frame["date"] = pd.to_datetime(
            frame["date"], format="%Y-%m-%d", errors="raise"
        ).dt.date
        if (
            frame["date"].duplicated().any()
            or not frame["date"].is_monotonic_increasing
        ):
            raise ValueError("INVALID_PRICE_DATES")
        for column in ("open", "close"):
            if any(
                type(v) is bool or not math.isfinite(float(v)) or float(v) <= 0
                for v in frame[column]
            ):
                raise ValueError("INVALID_PRICE_VALUE")
        assets[instrument] = frame
        hashes[str(source)] = spec["files"][instrument]["sha256"]
    if spec["actions"] is None:
        raise ValueError("CORPORATE_ACTION_MODEL_UNVERIFIED")
    action_path = _bound_file(spec["actions"])
    evidence = _read(action_path)
    if (
        set(evidence)
        != {
            "schema",
            "synthetic",
            "start",
            "end",
            "products",
            "events",
            "source",
            "review_id",
        }
        or evidence["schema"] != "competition.us_action_coverage.v1"
    ):
        raise ValueError("CORPORATE_ACTION_MODEL_UNVERIFIED")
    if evidence["events"] != []:
        raise ValueError("CORPORATE_ACTION_MODEL_UNSUPPORTED")
    if (
        sorted(evidence["products"]) != sorted(assets)
        or type(evidence["synthetic"]) is not bool
    ):
        raise ValueError("CORPORATE_ACTION_MODEL_UNVERIFIED")
    if spec["synthetic"]:
        if (
            evidence["synthetic"] is not True
            or evidence["source"] != "synthetic_contract_vector"
            or evidence["review_id"] is not None
        ):
            raise ValueError("CORPORATE_ACTION_MODEL_UNVERIFIED")
    elif (
        evidence["synthetic"] or spec["actions"]["sha256"] not in TRUSTED_ACTION_REVIEWS
    ):
        raise ValueError("CORPORATE_ACTION_MODEL_UNVERIFIED")
    start, end = (
        pd.Timestamp(evidence["start"]).date(),
        pd.Timestamp(evidence["end"]).date(),
    )
    if start > end or any(
        frame["date"].iloc[0] < start or frame["date"].iloc[-1] > end
        for frame in assets.values()
    ):
        raise ValueError("ACTION_COVERAGE_INTERVAL_MISMATCH")
    hashes[str(action_path)] = spec["actions"]["sha256"]
    if not isinstance(spec["schedule"], list) or not spec["schedule"]:
        raise ValueError("EMPTY_TARGET_SCHEDULE")
    return USNextSessionInputs(spec, assets, evidence, hashes)
