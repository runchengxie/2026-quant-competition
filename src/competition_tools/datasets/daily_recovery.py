"""Separately reserved recovery using validated pairs from a spent acquisition."""

import csv
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from .binance_daily import PRODUCTS, normalize_daily_archive
from .binance_daily_acquisition import inspect_daily_extension, reservation_path
from .binance_daily_spec import load_daily_plan, parent_rows
from .daily_storage import safe_path
from .storage import digest, spec_hash, write_json

BUDGET = dict(
    attempts=64, seconds=300, transferred_bytes=4 * 1024**2, per_response_bytes=32768
)


def inspect_cached_pairs(raw, resources):
    raw = safe_path(raw)
    allowed = {r["url"].rsplit("/", 1)[-1] for r in resources}
    if any(p.name not in allowed or not p.is_file() for p in raw.iterdir()):
        raise ValueError("UNLISTED_RECOVERY_RESPONSE")
    cached = []
    for resource in resources:
        name = resource["url"].rsplit("/", 1)[-1]
        if name.endswith(".CHECKSUM"):
            continue
        payload, checksum = safe_path(raw / name), safe_path(raw / (name + ".CHECKSUM"))
        if not payload.exists() or not checksum.exists():
            continue
        if any(
            p.stat().st_size > BUDGET["per_response_bytes"] for p in (payload, checksum)
        ):
            raise ValueError("RECOVERY_RESPONSE_LIMIT")
        normalize_daily_archive(
            payload.read_bytes(),
            checksum.read_text(encoding="ascii"),
            resource["product"],
            resource["day"],
        )
        cached.extend(
            dict(name=p.name, bytes=p.stat().st_size, sha256=digest(p))
            for p in (payload, checksum)
        )
    return cached


def _inputs(receipt):
    receipt = safe_path(receipt)
    previous = inspect_daily_extension(receipt)
    if previous["status"] != "blocked":
        raise ValueError("BLOCKED_ACQUISITION_REQUIRED")
    original = load_daily_plan(receipt.parent / "plan.json")
    cached = inspect_cached_pairs(receipt.parent / "raw", original["resources"])
    return receipt, previous, original, cached


def freeze_recovery(receipt, output, *, now):
    if now.tzinfo is None:
        raise ValueError("AWARE_RECOVERY_CLOCK_REQUIRED")
    receipt, previous, original, cached = _inputs(receipt)
    if original["end"] >= now.astimezone(timezone.utc).date().isoformat():
        raise ValueError("INCOMPLETE_RECOVERY_DAY")
    if len(original["resources"]) - len(cached) > BUDGET["attempts"]:
        raise ValueError("RECOVERY_REQUEST_LIMIT")
    value = dict(
        schema="competition.daily_recovery_plan.v1",
        frozen_at=now.isoformat(),
        previous_receipt=str(receipt),
        previous_receipt_sha256=digest(receipt),
        previous_attempts=previous["attempts"],
        previous_spend_uncertain=previous.get("spend_uncertain", False),
        original_plan=original,
        cached=cached,
        budget=dict(BUDGET),
        accepted_research=False,
    )
    value["plan_sha256"] = spec_hash(value)
    out = safe_path(output)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "plan.json", value)
    return value


def _load(path):
    plan = json.loads(safe_path(path).read_text(encoding="utf-8"))
    expected = spec_hash({k: v for k, v in plan.items() if k != "plan_sha256"})
    receipt, previous, original, cached = _inputs(Path(plan["previous_receipt"]))
    if (
        plan.get("schema") != "competition.daily_recovery_plan.v1"
        or plan.get("budget") != BUDGET
        or plan.get("plan_sha256") != expected
        or plan["previous_receipt_sha256"] != digest(receipt)
        or plan["original_plan"] != original
        or plan["cached"] != cached
        or plan["previous_attempts"] != previous["attempts"]
        or plan["previous_spend_uncertain"] != previous.get("spend_uncertain", False)
        or len(original["resources"]) - len(cached) > BUDGET["attempts"]
        or plan.get("accepted_research") is not False
    ):
        raise ValueError("RECOVERY_INPUT_CHANGED")
    return plan


def _reservation(plan):
    identity = spec_hash(
        {
            "previous_receipt_sha256": plan["previous_receipt_sha256"],
            "original_plan_sha256": plan["original_plan"]["plan_sha256"],
            "cached": plan["cached"],
            "budget": plan["budget"],
        }
    )
    return safe_path(
        reservation_path(plan["original_plan"]).parent.parent
        / "daily-recovery"
        / identity
    )


def acquire_recovery(config, plan_path, output, *, transport, clock=time.monotonic):
    plan = _load(plan_path)
    parent = safe_path(Path(plan["original_plan"]["parent_manifest"]))
    if not parent.is_relative_to(safe_path(config.data_root)):
        raise ValueError("RECOVERY_OWNER_MISMATCH")
    out, authority = safe_path(output), _reservation(plan)
    if out.exists() or authority.exists():
        raise ValueError("RECOVERY_ALREADY_SPENT_OR_UNCERTAIN")
    authority.mkdir(parents=True, exist_ok=False)
    out.mkdir(parents=True, exist_ok=False)
    (out / "raw").mkdir()
    (out / "normalized").mkdir()
    write_json(out / "plan.json", plan)
    started = clock()
    state = dict(
        schema="competition.daily_recovery_receipt.v1",
        plan_sha256=plan["plan_sha256"],
        status="reserved",
        attempts=0,
        transferred_bytes=0,
        reused_responses=len(plan["cached"]),
        previous_attempts=plan["previous_attempts"],
        previous_spend_uncertain=plan["previous_spend_uncertain"],
        in_flight=False,
        spend_uncertain=False,
        elapsed_seconds=0.0,
        accepted_research=False,
    )

    def checkpoint():
        state["elapsed_seconds"] = clock() - started
        write_json(authority / "receipt.json", state)
        write_json(out / "receipt.json", state)

    def remaining():
        checkpoint()
        seconds = BUDGET["seconds"] - state["elapsed_seconds"]
        if seconds <= 0 or state["transferred_bytes"] >= BUDGET["transferred_bytes"]:
            raise TimeoutError("RECOVERY_BUDGET_EXHAUSTED")
        return seconds

    checkpoint()
    try:
        cached = {r["name"]: r for r in plan["cached"]}
        old_raw = Path(plan["previous_receipt"]).parent / "raw"
        for resource in plan["original_plan"]["resources"]:
            seconds = remaining()
            name = resource["url"].rsplit("/", 1)[-1]
            target = out / "raw" / name
            if name in cached:
                shutil.copyfile(safe_path(old_raw / name), target)
                if digest(target) != cached[name]["sha256"]:
                    raise ValueError("RECOVERY_CACHE_CHANGED")
                continue
            if state["attempts"] >= BUDGET["attempts"]:
                raise ValueError("RECOVERY_ATTEMPTS_EXHAUSTED")
            state["attempts"] += 1
            state["in_flight"] = True
            checkpoint()
            limit = min(
                BUDGET["per_response_bytes"],
                BUDGET["transferred_bytes"] - state["transferred_bytes"],
            )
            status, body = transport.fetch(
                resource["url"], max_bytes=limit, timeout=seconds
            )
            if type(status) is not int or not isinstance(body, bytes):
                raise ValueError("UNKNOWN_RECOVERY_SPEND")
            state["transferred_bytes"] += len(body)
            state["in_flight"] = False
            remaining()
            if status != 200 or len(body) > limit:
                raise ValueError("RECOVERY_RESPONSE_BLOCKED")
            target.write_bytes(body)
        _, tables = parent_rows(parent)
        inspect_cached_pairs(out / "raw", plan["original_plan"]["resources"])
        for resource in plan["original_plan"]["resources"]:
            name = resource["url"].rsplit("/", 1)[-1]
            if not name.endswith(".CHECKSUM"):
                tables[resource["product"]].extend(
                    normalize_daily_archive(
                        (out / "raw" / name).read_bytes(),
                        (out / "raw" / (name + ".CHECKSUM")).read_text(
                            encoding="ascii"
                        ),
                        resource["product"],
                        resource["day"],
                    )
                )
        for product, rows in tables.items():
            with (out / "normalized" / f"{product}.csv").open(
                "w", encoding="utf-8", newline=""
            ) as stream:
                csv.writer(stream).writerows(
                    [["date", "open", "high", "low", "close", "volume"], *rows]
                )
        _load(plan_path)
        remaining()
        state.update(
            status="acquired", collected_at=datetime.now(timezone.utc).isoformat()
        )
        checkpoint()
        manifest = dict(
            schema="competition.daily_recovery_manifest.v1",
            plan=plan,
            receipt=dict(state),
            parent_status=plan["original_plan"]["parent_status"],
            coverage={
                p: dict(rows=len(r), start=r[0][0], end=r[-1][0])
                for p, r in tables.items()
            },
            files=[
                dict(
                    path=p.relative_to(out).as_posix(),
                    bytes=p.stat().st_size,
                    sha256=digest(p),
                )
                for d in ("raw", "normalized")
                for p in sorted((out / d).iterdir())
            ],
            accepted_research=False,
        )
        remaining()
        write_json(authority / "manifest.json", manifest)
        write_json(out / "manifest.json", manifest)
    except (OSError, ValueError, UnicodeError):
        state.update(status="blocked", spend_uncertain=state["in_flight"])
    finally:
        checkpoint()
        if state["elapsed_seconds"] >= BUDGET["seconds"]:
            state.update(status="blocked")
        if state["status"] != "acquired":
            (out / "manifest.json").unlink(missing_ok=True)
            (authority / "manifest.json").unlink(missing_ok=True)
        checkpoint()
    return state


def inspect_recovery(path):
    path = safe_path(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    plan = _load(path.parent / "plan.json")
    authority = _reservation(plan)
    terminal = json.loads((authority / "receipt.json").read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "competition.daily_recovery_manifest.v1"
        or manifest
        != json.loads((authority / "manifest.json").read_text(encoding="utf-8"))
        or manifest["plan"] != plan
        or manifest.get("accepted_research") is not False
        or terminal
        != json.loads((path.parent / "receipt.json").read_text(encoding="utf-8"))
        or terminal["status"] != "acquired"
        or terminal["in_flight"]
        or not 0
        <= manifest["receipt"]["elapsed_seconds"]
        <= terminal["elapsed_seconds"]
        < BUDGET["seconds"]
        or not 0 <= terminal["attempts"] <= BUDGET["attempts"]
        or not 0 <= terminal["transferred_bytes"] <= BUDGET["transferred_bytes"]
        or set(manifest["coverage"]) != PRODUCTS
    ):
        raise ValueError("INVALID_RECOVERY_MANIFEST")
    expected = {
        "raw/" + r["url"].rsplit("/", 1)[-1] for r in plan["original_plan"]["resources"]
    } | {f"normalized/{p}.csv" for p in PRODUCTS}
    actual = {
        p.relative_to(path.parent).as_posix()
        for d in ("raw", "normalized")
        for p in safe_path(path.parent / d).iterdir()
    }
    if (
        actual != expected
        or {r["path"] for r in manifest["files"]} != expected
        or len(manifest["files"]) != len(expected)
    ):
        raise ValueError("RECOVERY_INVENTORY_MISMATCH")
    for record in manifest["files"]:
        file = safe_path(path.parent / record["path"])
        if digest(file) != record["sha256"] or file.stat().st_size != record["bytes"]:
            raise ValueError("RECOVERY_PAYLOAD_CHANGED")
    return manifest
