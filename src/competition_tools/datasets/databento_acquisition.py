"""Exclusive single-attempt acquisition with private immutable evidence."""

import csv
import hashlib
import json
import os
import tomllib
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from ..project_storage import project_root, guarded_location

from .databento_quality import inspect_rows
from .databento_spec import (
    fingerprint,
    request_parameters,
    safe_path,
    validate_spec,
    checked_open,
    PathBinding,
)
from .databento_transport import DatabentoTransport, decimal_value, validate_cost_bound

MANIFEST = "competition.databento_dataset_manifest.v1"


def write_json(path, value):
    with checked_open(path, "x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False, default=str)
        stream.write("\n")


def digest(path):
    return hashlib.sha256(safe_path(path).read_bytes()).hexdigest()


def _mapping(rows, mappings, spec):
    if (
        not isinstance(mappings, dict)
        or mappings.get("not_found")
        or mappings.get("partial")
        or not isinstance(mappings.get("result"), dict)
        or set(mappings["result"]) != set(spec["symbols"])
    ):
        raise ValueError("PROVIDER_IDENTITY_UNVERIFIED")
    for row in rows:
        try:
            day = row["ts_event"][:10]
            entries = mappings["result"][row["symbol"]]
            matches = [e for e in entries if e["d0"] <= day < e["d1"]]
            if len(matches) != 1 or str(matches[0]["s"]) != row["instrument_id"]:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise ValueError("PROVIDER_IDENTITY_MISMATCH") from None


def _rate(prices):
    rates = []
    if isinstance(prices, list):
        for entry in prices:
            if not isinstance(entry, dict):
                raise ValueError("BILLING_BOUND_UNVERIFIED")
            mode = entry.get("mode", "").replace("_", "-").lower()
            if mode in ("historical", "historical-streaming"):
                rates.append(
                    decimal_value(entry.get("unit_prices", {}).get("ohlcv-1d"))
                )
    if not rates or any(r <= 0 for r in rates):
        raise ValueError("BILLING_BOUND_UNVERIFIED")
    return max(rates)


def acquire(spec: dict, destination: Path, *, transport=None, as_of=None) -> dict:
    validate_spec(spec)
    destination = safe_path(destination)
    # One workspace-level authorization, independent of selected artifact root.
    workspace_file = os.environ.get("WORKSPACE_CONFIG")
    if not workspace_file:
        raise ValueError("WORKSPACE_CONFIG_REQUIRED")
    workspace = tomllib.loads(
        safe_path(Path(workspace_file)).read_text(encoding="utf-8-sig")
    )
    owner = project_root(workspace["data_root"], workspace.get("project_data_root"))
    relative_guard = "authorizations/databento-us-2025-pilot.attempt.json"
    guard = safe_path(owner / relative_guard)
    guard.parent.mkdir(parents=True, exist_ok=True)
    if guard.exists():
        raise ValueError("PILOT_ATTEMPT_ALREADY_RESERVED")
    if destination.exists():
        raise ValueError("DATASET_VERSION_EXISTS")
    params = request_parameters(spec)
    identity = fingerprint(params)
    try:
        with guarded_location(owner, relative_guard):
            write_json(guard, {"request_sha256": identity, "destination": str(destination),
                               "state": "authorization_reserved"})
    except FileExistsError:
        raise ValueError("PILOT_ATTEMPT_ALREADY_RESERVED") from None
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    binding = PathBinding(destination)
    t = transport or DatabentoTransport(
        Path(spec["credential_file"]), spec["budget"], destination / "requests.jsonl"
    )
    # The transport starts before verification and finalization and is never reset.
    t.check_time()
    with checked_open(destination / ".owner", "x") as stream:
        stream.write(MANIFEST)
    write_json(destination / "spec.json", spec)
    now = as_of or datetime.now(timezone.utc)
    receipt = {
        "status": "blocked",
        "accepted_research": False,
        "issue_codes": [],
        "request_sha256": identity,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "observed_at": None,
        "historical_availability_verified": False,
        "cost": None,
    }
    try:
        # Authorization was durably reserved before setup/preflight; no resume.
        metadata = {}
        for method in (
            "metadata.get_cost",
            "metadata.get_billable_size",
            "metadata.get_record_count",
            "metadata.list_unit_prices",
            "symbology.resolve",
        ):
            binding.check()
            if method == "metadata.list_unit_prices":
                arguments = {"dataset": spec["dataset"]}
            elif method == "symbology.resolve":
                arguments = {
                    "dataset": spec["dataset"],
                    "symbols": ",".join(spec["symbols"]),
                    "stype_in": "raw_symbol",
                    "stype_out": "instrument_id",
                    "start_date": spec["start"],
                    "end_date": spec["end"],
                }
            else:
                arguments = params
            metadata[method] = t.get_metadata(method, arguments)
        receipt["cost"] = validate_cost_bound(
            metadata["metadata.get_cost"],
            {
                "unit_price_usd_per_gb": _rate(metadata["metadata.list_unit_prices"]),
                "billable_bytes": metadata["metadata.get_billable_size"],
                "record_count": metadata["metadata.get_record_count"],
                "request_sha256": identity,
                "quote_request_sha256": identity,
            },
            Decimal("0.10"),
        )
        write_json(destination / "preflight.json", metadata)
        mappings = metadata["symbology.resolve"]
        _mapping([], mappings, spec)
        t.check_time()
        # Separate durable marker identifies that the billable call may have started.
        write_json(destination / "download-attempt.json", {"request_sha256": identity})
        raw = destination / "raw/bars.csv"
        t.download_csv(params, raw)
        binding.check()
        receipt["observed_at"] = datetime.now(timezone.utc).isoformat()
        with checked_open(raw, "r", encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) >= 4000 or len(rows) != metadata["metadata.get_record_count"]:
            raise ValueError("RECORD_COUNT_MISMATCH")
        _mapping(rows, mappings, spec)
        from .session_calendar import completed_sessions

        try:
            sessions = completed_sessions(
                "XNYS", spec["start"], "2025-12-31", as_of=now
            )
        except ValueError:
            sessions = {"sessions": None, "calendar_name": "XNYS"}
        # Common reference schedule is not proof of each instrument's listing venue.
        sessions["listing_verified"] = False
        quality = inspect_rows(rows, spec, sessions)
        tables = quality.pop("normalized")
        write_json(destination / "coverage.json", quality)
        for symbol, values in tables.items():
            binding.check()
            target = destination / "normalized" / f"{symbol}.csv"
            target.parent.mkdir(exist_ok=True)
            with checked_open(target, "x", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["date", "open", "high", "low", "close", "volume"])
                writer.writerows(values)
        receipt["issue_codes"] = quality["issue_codes"]
        receipt["status"] = "partial" if quality["issue_codes"] else "acquired"
        t.check_time()
    except ValueError as exc:
        # Internal code-only errors. Never propagate arbitrary provider messages.
        code = str(exc)
        receipt["issue_codes"] = [
            code if code.isupper() and len(code) < 100 else "PILOT_VALIDATION_FAILED"
        ]
    except Exception:
        receipt["issue_codes"] = ["PILOT_ACQUISITION_FAILED"]
    try:
        t.check_time()
    except ValueError:
        receipt["status"] = "blocked"
        receipt["issue_codes"] = ["TIME_BUDGET"]
    binding.check()
    receipt["spent"] = t.spent()
    write_json(destination / "receipt.json", receipt)
    files = [
        {"path": p.relative_to(destination).as_posix(), "sha256": digest(p)}
        for p in sorted(destination.rglob("*"))
        if p.is_file()
    ]
    manifest = {
        "schema": MANIFEST,
        "spec": spec,
        "receipt": receipt,
        "files": files,
        "accepted_research": False,
    }
    write_json(destination / "manifest.json", manifest)
    # Charge finalization to the same origin; overruns cannot yield usable output.
    try:
        t.check_time()
    except ValueError:
        write_json(destination / ".deadline-exceeded", {"status": "blocked"})
        return {
            "status": "blocked",
            "manifest": str(destination / "manifest.json"),
            "issue_codes": ["TIME_BUDGET"],
            "accepted_research": False,
        }
    return {**receipt, "manifest": str(destination / "manifest.json")}


def verify_manifest(path: Path) -> dict:
    path = safe_path(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "spec", "receipt", "files", "accepted_research"}
        or value["schema"] != MANIFEST
        or value["accepted_research"] is not False
        or (path.parent / ".deadline-exceeded").exists()
    ):
        raise ValueError("INVALID_DATABENTO_MANIFEST")
    validate_spec(value["spec"])
    receipt = value["receipt"]
    required = {
        "status",
        "accepted_research",
        "issue_codes",
        "request_sha256",
        "started_at",
        "observed_at",
        "historical_availability_verified",
        "cost",
        "spent",
    }
    if (
        not isinstance(receipt, dict)
        or set(receipt) != required
        or receipt["status"] not in ("blocked", "partial", "acquired")
        or receipt["accepted_research"] is not False
        or receipt["historical_availability_verified"] is not False
        or not isinstance(receipt["issue_codes"], list)
        or any(
            not isinstance(c, str) or not c.isupper() for c in receipt["issue_codes"]
        )
        or (receipt["status"] == "acquired") != (not receipt["issue_codes"])
        or not isinstance(receipt["spent"], dict)
        or set(receipt["spent"])
        != {"metadata_requests", "download_requests", "bytes", "seconds"}
    ):
        raise ValueError("INVALID_DATABENTO_RECEIPT")
    spent = receipt["spent"]
    for field, cap in [
        ("metadata_requests", 5),
        ("download_requests", 1),
        ("bytes", 20971521),
    ]:
        if type(spent[field]) is not int or not 0 <= spent[field] <= cap:
            raise ValueError("INVALID_DATABENTO_RECEIPT")
    decimal_value(spent["seconds"])
    started = datetime.fromisoformat(receipt["started_at"])
    if started.tzinfo is None:
        raise ValueError("INVALID_DATABENTO_RECEIPT")
    if receipt["observed_at"] is not None:
        observed = datetime.fromisoformat(receipt["observed_at"])
        if observed.tzinfo is None or observed < started:
            raise ValueError("INVALID_DATABENTO_RECEIPT")
    expected = set()
    for record in value["files"]:
        relative = Path(record["path"])
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or record["path"] in expected
        ):
            raise ValueError("INVALID_MANIFEST_PATH")
        expected.add(record["path"])
        if digest(path.parent / relative) != record["sha256"]:
            raise ValueError("MANIFEST_HASH_MISMATCH")
    actual = {
        p.relative_to(path.parent).as_posix()
        for p in path.parent.rglob("*")
        if p.is_file() and p != path
    }
    if actual != expected:
        raise ValueError("MANIFEST_FILE_SET_MISMATCH")
    if not {".owner", "spec.json", "receipt.json"} <= expected:
        raise ValueError("MANIFEST_ARTIFACTS_MISSING")
    if (path.parent / ".owner").read_text() != MANIFEST:
        raise ValueError("INVALID_DATABENTO_OWNER")
    if (
        json.loads((path.parent / "receipt.json").read_text()) != value["receipt"]
        or json.loads((path.parent / "spec.json").read_text()) != value["spec"]
        or value["receipt"]["accepted_research"] is not False
        or value["receipt"]["request_sha256"]
        != fingerprint(request_parameters(value["spec"]))
    ):
        raise ValueError("MANIFEST_RECEIPT_MISMATCH")
    if receipt["status"] in ("partial", "acquired"):
        required_files = {
            "preflight.json",
            "raw/bars.csv",
            "coverage.json",
            "download-attempt.json",
        }
        required_files.update(f"normalized/{s}.csv" for s in value["spec"]["symbols"])
        if not required_files <= expected or receipt["observed_at"] is None:
            raise ValueError("MANIFEST_ARTIFACTS_MISSING")
        metadata = json.loads((path.parent / "preflight.json").read_text())
        identity = fingerprint(request_parameters(value["spec"]))
        cost = validate_cost_bound(
            metadata["metadata.get_cost"],
            {
                "unit_price_usd_per_gb": _rate(metadata["metadata.list_unit_prices"]),
                "billable_bytes": metadata["metadata.get_billable_size"],
                "record_count": metadata["metadata.get_record_count"],
                "request_sha256": identity,
                "quote_request_sha256": identity,
            },
            Decimal("0.10"),
        )
        if (
            receipt["cost"] != cost
            or spent["metadata_requests"] != 5
            or spent["download_requests"] != 1
        ):
            raise ValueError("MANIFEST_COST_MISMATCH")
        with safe_path(path.parent / "raw/bars.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != metadata["metadata.get_record_count"]:
            raise ValueError("RECORD_COUNT_MISMATCH")
        _mapping(rows, metadata["symbology.resolve"], value["spec"])
        coverage = json.loads((path.parent / "coverage.json").read_text())
        # This v1 pilot has no authoritative per-instrument listing evidence.
        if coverage.get("calendar", {}).get("listing_verified") is not False:
            raise ValueError("UNSUPPORTED_LISTING_EVIDENCE")
        quality = inspect_rows(rows, value["spec"], coverage["calendar"])
        normalized = quality.pop("normalized")
        if coverage != quality or receipt["issue_codes"] != quality["issue_codes"]:
            raise ValueError("MANIFEST_QUALITY_MISMATCH")
        if receipt["status"] != ("partial" if quality["issue_codes"] else "acquired"):
            raise ValueError("MANIFEST_STATUS_MISMATCH")
        for symbol, expected_rows in normalized.items():
            with safe_path(path.parent / f"normalized/{symbol}.csv").open(
                newline=""
            ) as stream:
                actual_rows = list(csv.reader(stream))
            if actual_rows != [
                ["date", "open", "high", "low", "close", "volume"],
                *expected_rows,
            ]:
                raise ValueError("NORMALIZATION_MISMATCH")
    return value
