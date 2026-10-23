"""Exclusive single-attempt acquisition with private immutable evidence."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .databento_quality import inspect_rows
from .databento_spec import fingerprint, request_parameters, safe_path, validate_spec
from .databento_transport import DatabentoTransport, decimal_value, validate_cost_bound

MANIFEST = "competition.databento_dataset_manifest.v1"


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
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
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Guard is independent of version/destination name and survives failures.
    guard = destination.parent / ".databento-us-2025-pilot.attempt"
    if guard.exists():
        raise ValueError("PILOT_ATTEMPT_ALREADY_RESERVED")
    if destination.exists():
        raise ValueError("DATASET_VERSION_EXISTS")
    destination.mkdir()
    t = transport or DatabentoTransport(
        Path(spec["credential_file"]), spec["budget"], destination / "requests.jsonl"
    )
    # The transport starts before verification and finalization and is never reset.
    t.check_time()
    with (destination / ".owner").open("x") as stream:
        stream.write(MANIFEST)
    write_json(destination / "spec.json", spec)
    params = request_parameters(spec)
    identity = fingerprint(params)
    now = as_of or datetime.now(timezone.utc)
    receipt = {
        "status": "blocked",
        "accepted_research": False,
        "issue_codes": [],
        "request_sha256": identity,
        "observed_at": now.isoformat(),
        "historical_availability_verified": False,
        "cost": None,
    }
    try:
        # Reserve one authorization even for an interrupted preflight. No resume.
        write_json(
            guard,
            {
                "request_sha256": identity,
                "destination": str(destination),
                "state": "authorization_reserved",
            },
        )
        metadata = {}
        for method in (
            "metadata.get_cost",
            "metadata.get_billable_size",
            "metadata.get_record_count",
            "metadata.list_unit_prices",
            "symbology.resolve",
        ):
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
        with raw.open(encoding="utf-8-sig", newline="") as stream:
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
            target = destination / "normalized" / f"{symbol}.csv"
            target.parent.mkdir(exist_ok=True)
            with target.open("x", newline="", encoding="utf-8") as stream:
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
    if (
        json.loads((path.parent / "receipt.json").read_text()) != value["receipt"]
        or json.loads((path.parent / "spec.json").read_text()) != value["spec"]
        or value["receipt"]["accepted_research"] is not False
        or value["receipt"]["request_sha256"]
        != fingerprint(request_parameters(value["spec"]))
    ):
        raise ValueError("MANIFEST_RECEIPT_MISMATCH")
    return value
