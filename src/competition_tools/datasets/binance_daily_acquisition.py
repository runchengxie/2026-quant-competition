"""One reserved extension, no automatic retries or implicit availability grant."""

import csv
import io
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .binance_daily import normalize_daily_archive
from .binance_daily_spec import load_daily_plan, parent_rows
from .daily_storage import safe_path
from .storage import digest, spec_hash, write_json


def reservation_path(plan: dict) -> Path:
    parent = safe_path(Path(plan["parent_manifest"]))
    owners = [p.parent for p in parent.parents if p.name == "datasets"]
    owner = owners[0] if owners else parent.parent.parent
    identity = spec_hash({k: plan[k] for k in ("parent_sha256", "start", "end")})
    return safe_path(owner / "acquisition-ledgers" / "daily-extension" / identity)


def acquire_daily_extension(config, plan_path: Path, output: Path, *, transport) -> dict:
    plan = load_daily_plan(plan_path)
    reservation = reservation_path(plan)
    if reservation.exists():
        raise ValueError("DAILY_RESERVATION_ALREADY_SPENT_OR_UNCERTAIN")
    parent = safe_path(Path(plan["parent_manifest"]))
    if not parent.is_relative_to(safe_path(config.data_root)):
        raise ValueError("DAILY_RESERVATION_OWNER_MISMATCH")
    out = safe_path(output)
    if out.exists():
        raise FileExistsError("DAILY_EXTENSION_OUTPUT_EXISTS")
    reservation.parent.mkdir(parents=True, exist_ok=True)
    reservation.mkdir(exist_ok=False)
    started = time.monotonic()
    state = dict(schema="competition.binance_daily_receipt.v1", plan_sha256=plan["plan_sha256"], attempts=0, transferred_bytes=0, expanded_bytes=0, elapsed_seconds=0.0, in_flight=False, status="reserved", issue_codes=[], accepted_research=False)

    def checkpoint():
        state["elapsed_seconds"] = time.monotonic() - started
        write_json(reservation / "receipt.json", state)

    checkpoint()
    out.mkdir(parents=True, exist_ok=False)
    (out / "raw").mkdir()
    (out / "normalized").mkdir()
    budget = plan["budget"]
    try:
        _, tables = parent_rows(parent)
        if digest(parent) != plan["parent_sha256"]:
            raise ValueError("DAILY_PARENT_CHANGED")
        bodies = {}
        for resource in plan["resources"]:
            checkpoint()
            remaining = budget["seconds"] - state["elapsed_seconds"]
            left = budget["transferred_bytes"] - state["transferred_bytes"]
            if remaining <= 0 or left <= 0 or state["attempts"] >= budget["attempts"]:
                raise ValueError("DAILY_BUDGET_EXHAUSTED")
            state["attempts"] += 1
            state["in_flight"] = True
            checkpoint()
            status, body = transport.fetch(resource["url"], max_bytes=min(left, budget["per_zip_bytes"]), timeout=remaining)
            if type(status) is not int or not isinstance(body, bytes):
                raise ValueError("UNKNOWN_DAILY_RESPONSE")
            state["transferred_bytes"] += len(body)
            state["in_flight"] = False
            checkpoint()
            if status != 200 or state["transferred_bytes"] > budget["transferred_bytes"] or state["elapsed_seconds"] >= budget["seconds"]:
                raise ValueError("DAILY_RESPONSE_OR_BUDGET_BLOCKED")
            name = resource["url"].rsplit("/", 1)[-1]
            (out / "raw" / name).write_bytes(body)
            key = (resource["product"], resource["day"])
            if name.endswith(".CHECKSUM"):
                payload = bodies.pop(key)
                rows = normalize_daily_archive(payload, body.decode("ascii"), *key)
                with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                    state["expanded_bytes"] += archive.infolist()[0].file_size
                if state["expanded_bytes"] > budget["expanded_bytes"]:
                    raise ValueError("DAILY_EXPANSION_BUDGET")
                tables[key[0]].extend(rows)
            else:
                bodies[key] = body
        for product, rows in tables.items():
            with (out / "normalized" / f"{product}.csv").open("w", encoding="utf-8", newline="") as stream:
                csv.writer(stream).writerows([["date", "open", "high", "low", "close", "volume"], *rows])
        checkpoint()
        if state["elapsed_seconds"] >= budget["seconds"] or digest(parent) != plan["parent_sha256"]:
            raise ValueError("DAILY_FINALIZATION_BLOCKED")
        state.update(status="acquired", collected_at=datetime.now(timezone.utc).isoformat())
        files = [dict(path=p.relative_to(out).as_posix(), sha256=digest(p), bytes=p.stat().st_size) for directory in ("raw", "normalized") for p in sorted((out / directory).iterdir())]
        manifest = dict(schema="competition.binance_daily_manifest.v1", plan=plan, parent_status=plan["parent_status"], coverage={p: dict(rows=len(rows), start=rows[0][0], end=rows[-1][0]) for p, rows in tables.items()}, files=files, accepted_research=False)
        checkpoint()
        if state["elapsed_seconds"] >= budget["seconds"]:
            raise ValueError("DAILY_FINALIZATION_DEADLINE")
        manifest["receipt"] = dict(state)
        write_json(out / "manifest.json", manifest)
    except (ValueError, OSError, TimeoutError, UnicodeError, zipfile.BadZipFile):
        state.update(status="blocked", issue_codes=["DAILY_EXTENSION_BLOCKED"], spend_uncertain=state["in_flight"])
        (out / "manifest.json").unlink(missing_ok=True)
    finally:
        checkpoint()
        write_json(out / "receipt.json", state)
    return state


def inspect_daily_extension(manifest_path: Path) -> dict:
    path = safe_path(manifest_path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema") != "competition.binance_daily_manifest.v1" or value.get("accepted_research") is not False or value.get("receipt", {}).get("status") != "acquired":
        raise ValueError("INVALID_DAILY_EXTENSION_MANIFEST")
    for record in value["files"]:
        relative = Path(record["path"])
        if relative.is_absolute() or len(relative.parts) != 2 or relative.parts[0] not in {"raw", "normalized"} or ".." in relative.parts:
            raise ValueError("INVALID_DAILY_EXTENSION_PATH")
        file = safe_path(path.parent / relative)
        if file.stat().st_size != record["bytes"] or digest(file) != record["sha256"]:
            raise ValueError("DAILY_EXTENSION_HASH_MISMATCH")
    return value
