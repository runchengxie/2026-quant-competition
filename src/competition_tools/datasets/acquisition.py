"""Checkpointed acquisition, with explicit gaps rather than fabricated history."""

import calendar
import csv
import json
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from .binance import archive_url, normalize_archive
from .quality import validate_bars
from .storage import digest, spec_hash, write_json
from .transport import DatasetBlocked, Transport


def months(start: str, end: str) -> list[str]:
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    current = first.replace(day=1)
    today = datetime.now(timezone.utc).date().replace(day=1)
    result = []
    while current <= last and current < today:
        result.append(current.strftime("%Y-%m"))
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
    return result


def acquire(spec: dict, staging: Path) -> dict:
    staging.mkdir(parents=True, exist_ok=True)
    marker = staging / ".dataset-owner"
    identity = staging / "spec-hash.txt"
    fingerprint = spec_hash(spec)
    if marker.exists():
        if (
            marker.read_text() != "competition.dataset.v1"
            or identity.read_text() != fingerprint
        ):
            raise ValueError("STAGING_SPEC_MISMATCH")
    elif list(staging.iterdir()):
        raise ValueError("UNOWNED_STAGING")
    else:
        marker.write_text("competition.dataset.v1")
        identity.write_text(fingerprint)
    if spec["source"] == "licensed_import":
        return import_licensed(spec, staging)
    if spec["source"] == "ibkr":
        from .ibkr import acquire as acquire_broker

        return acquire_broker(spec, staging)
    if spec["source"] != "binance_spot":
        raise DatasetBlocked("PROVIDER_CONTRACT_UNVERIFIED")
    transport = Transport(spec["budget"], staging / "requests.jsonl")
    checkpoint_file = staging / "chunks.json"
    chunks = json.loads(checkpoint_file.read_text()) if checkpoint_file.exists() else {}
    # Verify previously completed bytes before any resume, including normalization lineage.
    for item in chunks.values():
        for record in item.get("files", []):
            path = staging / record["path"]
            if not path.is_file() or digest(path) != record["sha256"]:
                raise ValueError("CHECKPOINT_HASH_MISMATCH")
    gaps, coverage = [], {}
    stop = False
    for product in spec["products"]:
        all_rows = []
        for month in months(spec["start"], spec["end"]):
            key = product + "/" + month
            filename = f"{product}-1d-{month}.zip"
            raw = staging / "raw" / product / filename
            checksum = raw.with_name(filename + ".CHECKSUM")
            try:
                completed = {f["path"] for f in chunks.get(key, {}).get("files", [])}
                for path, url in (
                    (raw, archive_url(product, month)),
                    (checksum, archive_url(product, month) + ".CHECKSUM"),
                ):
                    relative = path.relative_to(staging).as_posix()
                    if relative not in completed:
                        # An interrupted uncheckpointed write cannot be silently trusted.
                        if path.exists():
                            raise ValueError("UNCHECKPOINTED_RAW_FILE")
                        transport.fetch(url, path)
                        chunks.setdefault(key, {"files": []})["files"].append(
                            {"path": relative, "sha256": digest(path)}
                        )
                        write_json(checkpoint_file, chunks)
                rows = normalize_archive(
                    raw.read_bytes(), checksum.read_text(), product, month
                )
                all_rows.extend(r for r in rows if spec["start"] <= r[0] <= spec["end"])
                expected = calendar.monthrange(int(month[:4]), int(month[5:]))[1]
                if len(rows) != expected:
                    gaps.append(
                        {
                            "product": product,
                            "month": month,
                            "reason": "INCOMPLETE_MONTH",
                            "rows": len(rows),
                        }
                    )
            except DatasetBlocked as error:
                reason = str(error)
                gaps.append({"product": product, "month": month, "reason": reason})
                if reason != "ARCHIVE_NOT_AVAILABLE":
                    stop = True
                    break
        if all_rows:
            validate_bars(all_rows)
            target = staging / "normalized" / f"{product}.csv"
            target.parent.mkdir(exist_ok=True)
            with target.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["date", "open", "high", "low", "close", "volume"])
                writer.writerows(all_rows)
            coverage[product] = {
                "rows": len(all_rows),
                "start": all_rows[0][0],
                "end": all_rows[-1][0],
            }
        if stop:
            break
    for product in spec["products"]:
        if product not in coverage:
            gaps.append({"product": product, "reason": "NO_VALID_BARS"})
    effective_end = max((v["end"] for v in coverage.values()), default=None)
    if effective_end != spec["end"]:
        gaps.append({"reason": "REQUESTED_END_NOT_COVERED"})
    receipt = {
        "schema": "competition.dataset_receipt.v1",
        "source": spec["source"],
        "spec_hash": fingerprint,
        "status": "partial" if gaps else "acquired",
        "coverage": coverage,
        "gaps": gaps,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "available_at": None,
        "requests": transport.requests,
        "downloaded_bytes": transport.bytes,
        "normalization": "binance-spot-daily.v1",
        "universe_status": spec["universe_status"],
        "accepted_research": False,
    }
    write_json(staging / "receipt.json", receipt)
    return receipt


def import_licensed(spec: dict, staging: Path) -> dict:
    import time
    from competition_tools.team.paths import validate_external
    from .membership import load_membership

    source = validate_external(Path(spec["input_directory"]))
    coverage, gaps = {}, []
    total_bytes = 0
    started = time.monotonic()
    if spec["universe_status"] == "point_in_time":
        if not spec.get("membership_file"):
            raise DatasetBlocked("PIT_MEMBERSHIP_MISSING")
        membership = validate_external(Path(spec["membership_file"]))
        records = load_membership(membership, status="point_in_time")
        if any(not r["available_at"] for r in records):
            raise DatasetBlocked("PIT_AVAILABILITY_UNKNOWN")
        (staging / "membership.csv").write_bytes(membership.read_bytes())
    for product in spec["products"]:
        if time.monotonic() - started >= spec["budget"]["seconds"]:
            raise DatasetBlocked("TIME_BUDGET")
        path = source / f"{product}.csv"
        if not path.is_file() or path.is_symlink():
            gaps.append({"product": product, "reason": "INPUT_MISSING"})
            continue
        total_bytes += path.stat().st_size
        if total_bytes > spec["budget"]["bytes"]:
            raise DatasetBlocked("BYTE_BUDGET")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            if next(reader) != ["date", "open", "high", "low", "close", "volume"]:
                raise ValueError("INVALID_BAR_COLUMNS")
            rows = list(reader)
        validate_bars(rows)
        rows = [r for r in rows if spec["start"] <= r[0] <= spec["end"]]
        if not rows:
            gaps.append({"product": product, "reason": "EMPTY_INPUT"})
            continue
        target = staging / "normalized" / path.name
        target.parent.mkdir(exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["date", "open", "high", "low", "close", "volume"])
            writer.writerows(rows)
        coverage[product] = {
            "rows": len(rows),
            "start": rows[0][0],
            "end": rows[-1][0],
            "input_sha256": digest(path),
        }
    receipt = {
        "schema": "competition.dataset_receipt.v1",
        "source": spec["source"],
        "spec_hash": spec_hash(spec),
        "status": "partial" if gaps else "acquired",
        "coverage": coverage,
        "gaps": gaps,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "available_at": None,
        "normalization": "licensed-daily-csv.v1",
        "accepted_research": False,
    }
    write_json(staging / "receipt.json", receipt)
    return receipt
