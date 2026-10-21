"""Sequential daily backfill with explicit budgets and verified checkpoints."""

import csv
import io
import json
import os
from contextlib import contextmanager
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from competition_tools.team.paper_session import PaperReadError, PaperReadSession
from competition_tools.team.gateway_verification import _stock, _matches
from .daily_spec import validate_daily_spec
from .daily_storage import OWNER, safe_path, payload_files, verify_files
from .quality import validate_bars
from .session_calendar import completed_sessions
from .storage import spec_hash, write_json


class StopCollection(ValueError):
    pass


def _windows(start, end):
    lower, final = date.fromisoformat(start), date.fromisoformat(end)
    while lower <= final:
        upper = min(date(lower.year, 12, 31), final)
        yield lower.isoformat(), upper.isoformat()
        lower = upper + timedelta(days=1)


def _normalized(rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["date", "open", "high", "low", "close", "volume"])
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def collect_daily(
    spec: dict,
    staging: Path,
    *,
    session_factory=PaperReadSession,
    clock=time.monotonic,
    sleep=time.sleep,
) -> dict:
    with collection_lock(staging):
        return _collect_daily(
            spec, staging, session_factory=session_factory, clock=clock, sleep=sleep
        )


@contextmanager
def collection_lock(staging):
    staging = safe_path(staging)
    staging.parent.mkdir(parents=True, exist_ok=True)
    lock = safe_path(staging.with_name(staging.name + ".collection-lock"))
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError("COLLECTION_IN_PROGRESS") from None
    try:
        yield
    finally:
        os.close(fd)
        lock.unlink()


def _collect_daily(spec, staging, *, session_factory, clock, sleep):
    began = clock()
    validate_daily_spec(spec)
    staging = safe_path(staging)
    if (staging / "manifest.json").exists():
        raise ValueError("DATASET_VERSION_EXISTS")
    staging.mkdir(parents=True, exist_ok=True)
    owner = staging / ".dataset-owner"
    checkpoint = staging / "checkpoint.json"
    if owner.exists():
        safe_path(owner)
        if owner.read_text() != OWNER or not checkpoint.exists():
            raise ValueError("UNOWNED_STAGING")
        state = json.loads(safe_path(checkpoint).read_text())
        if state["spec_hash"] != spec_hash(spec):
            raise ValueError("SPEC_HASH_MISMATCH")
        verify_files(staging, state["files"])
    else:
        if any(staging.iterdir()):
            raise ValueError("UNOWNED_STAGING")
        owner.write_text(OWNER)
        state = {
            "spec_hash": spec_hash(spec),
            "requests": 0,
            "elapsed_seconds": 0,
            "done": [],
            "files": [],
            "resolved_contracts": {},
        }
        write_json(checkpoint, state)
    for directory in ("raw", "normalized"):
        safe_path(staging / directory).mkdir(exist_ok=True)
    observed = datetime.now(timezone.utc)
    calendar = completed_sessions(
        spec["calendar"], spec["start"], spec["end"], as_of=observed
    )
    sessions = calendar["sessions"]
    if not sessions:
        raise ValueError("NO_COMPLETED_SESSIONS")
    if state.get("calendar") not in (None, calendar):
        raise ValueError("CALENDAR_CHANGED_RESUME_NEW_VERSION_REQUIRED")
    state["calendar"] = calendar
    prior_elapsed = state["elapsed_seconds"]
    last_start = clock() if state["requests"] else None
    issues = []

    def save(*, refresh_files=True):
        if refresh_files:
            state["files"] = payload_files(staging)
        state["elapsed_seconds"] = prior_elapsed + max(0, clock() - began)
        write_json(checkpoint, state)

    def budget_request():
        nonlocal last_start
        if state["requests"] >= spec["budget"]["requests"]:
            raise StopCollection("REQUEST_BUDGET")
        if last_start is not None:
            pause = max(0, 10 - (clock() - last_start))
            if prior_elapsed + clock() - began + pause >= spec["budget"]["seconds"]:
                raise StopCollection("TIME_BUDGET")
            sleep(pause)
        remaining = spec["budget"]["seconds"] - prior_elapsed - (clock() - began)
        if remaining <= 0:
            raise StopCollection("TIME_BUDGET")
        state["requests"] += 1
        last_start = clock()
        save()
        return min(60, remaining)

    rows_by_product = {}
    for contract in spec["contracts"]:
        product = contract["product"]
        normalized = staging / "normalized" / f"{product}.csv"
        rows_by_product[product] = (
            list(csv.reader(io.StringIO(normalized.read_text())))[1:]
            if normalized.exists()
            else []
        )
    try:
        remaining_connection = (
            spec["budget"]["seconds"] - prior_elapsed - (clock() - began)
        )
        if remaining_connection <= 0:
            raise StopCollection("TIME_BUDGET")
        with session_factory(
            Path(spec["connection_file"]), timeout=min(8, remaining_connection)
        ) as client:
            client.RaiseRequestErrors = True
            for definition in spec["contracts"]:
                product = definition["product"]
                full_windows = [
                    (a, b)
                    for a, b in _windows(sessions[0], sessions[-1])
                    if any(a <= s <= b for s in sessions)
                ]
                windows = full_windows.copy()
                refresh = state.get("refresh")
                if refresh and product not in state.get("rebuild_products", []):
                    windows = list(_windows(refresh["overlap_start"], sessions[-1]))
                if all(f"{product}:{a}:{b}" in state["done"] for a, b in windows):
                    continue
                client.RequestTimeout = budget_request()
                qualified = client.qualifyContracts(_stock(definition))
                if len(qualified) != 1 or not _matches(qualified[0], definition):
                    raise StopCollection("CONTRACT_MISMATCH")
                resolved = {"con_id": qualified[0].conId, **definition}
                if (
                    product in state["resolved_contracts"]
                    and state["resolved_contracts"][product] != resolved
                ):
                    raise StopCollection("CONTRACT_IDENTITY_CHANGED")
                state["resolved_contracts"][product] = resolved
                for lower, upper in windows:
                    key = f"{product}:{lower}:{upper}"
                    if key in state["done"]:
                        continue
                    timeout = budget_request()
                    client.RequestTimeout = timeout
                    # A year is bounded, including leap years; filter the exact
                    # requested session interval after the provider response.
                    end = date.fromisoformat(upper) + timedelta(days=1)
                    bars = client.reqHistoricalData(
                        qualified[0],
                        endDateTime=end.strftime("%Y%m%d 00:00:00")
                        + " "
                        + spec["timezone"],
                        durationStr="1 Y"
                        if (date.fromisoformat(upper) - date.fromisoformat(lower)).days
                        >= 365
                        else f"{(date.fromisoformat(upper) - date.fromisoformat(lower)).days + 1} D",
                        barSizeSetting="1 day",
                        whatToShow="TRADES",
                        useRTH=True,
                        formatDate=1,
                        keepUpToDate=False,
                        timeout=timeout,
                    )
                    remaining = (
                        spec["budget"]["seconds"] - prior_elapsed - (clock() - began)
                    )
                    if remaining <= 0:
                        raise StopCollection("TIME_BUDGET")
                    rows = [
                        [
                            bar.date.isoformat()
                            if isinstance(bar.date, date)
                            else str(bar.date),
                            *[
                                str(getattr(bar, k))
                                for k in ("open", "high", "low", "close", "volume")
                            ],
                        ]
                        for bar in bars
                    ]
                    try:
                        validate_bars(rows)
                    except (ValueError, TypeError, OverflowError):
                        raise StopCollection("INVALID_BARS") from None
                    raw_bytes = (
                        json.dumps(rows, allow_nan=False, separators=(",", ":")) + "\n"
                    ).encode()
                    by_date = {r[0]: r for r in rows_by_product[product]}
                    if refresh and product not in state.get("rebuild_products", []):
                        overlap_old = {
                            day: row
                            for day, row in by_date.items()
                            if lower <= day <= upper
                        }
                        overlap_new = {r[0]: r for r in rows if r[0] in overlap_old}
                        if overlap_new != overlap_old:
                            state["rebuild_products"].append(product)
                            state["revisions"].append(
                                {
                                    "product": product,
                                    "action": "full_rebuild",
                                    "reason": "OVERLAP_CHANGED",
                                }
                            )
                            rows_by_product[product] = []
                            (staging / "normalized" / f"{product}.csv").write_bytes(
                                _normalized([])
                            )
                            by_date = {}
                            windows.extend(
                                w for w in full_windows if w != (lower, upper)
                            )
                            save()
                    for row in rows:
                        if lower <= row[0] <= upper:
                            if row[0] not in sessions:
                                raise StopCollection("NONSESSION_BAR")
                            if row[0] in by_date and by_date[row[0]] != row:
                                raise StopCollection("CONFLICTING_BAR")
                            by_date[row[0]] = row
                    combined = [by_date[k] for k in sorted(by_date)]
                    normalized_bytes = _normalized(combined)
                    raw = staging / "raw" / f"{product}-{lower}-{upper}.json"
                    normalized = staging / "normalized" / f"{product}.csv"
                    current_bytes = sum(f["bytes"] for f in payload_files(staging))
                    total = (
                        current_bytes
                        + len(raw_bytes)
                        + len(normalized_bytes)
                        - (normalized.stat().st_size if normalized.exists() else 0)
                        - (raw.stat().st_size if raw.exists() else 0)
                    )
                    if total > spec["budget"]["bytes"]:
                        raise StopCollection("BYTE_BUDGET")
                    if prior_elapsed + clock() - began >= spec["budget"]["seconds"]:
                        raise StopCollection("TIME_BUDGET")
                    # Persist the request payload before acknowledging it in the
                    # checkpoint; an interrupted write is rejected on resume.
                    raw.write_bytes(raw_bytes)
                    normalized.write_bytes(normalized_bytes)
                    rows_by_product[product] = combined
                    expected_chunk = {s for s in sessions if lower <= s <= upper}
                    if expected_chunk <= {r[0] for r in rows}:
                        state["done"].append(key)
                    save()
                    if not rows:
                        raise StopCollection("HISTORICAL_UNAVAILABLE")
    except StopCollection as error:
        issues.append(str(error))
    except PaperReadError as error:
        issues.append(str(error))
    except Exception as error:
        # Numeric broker codes are useful without retaining private messages.
        code = getattr(error, "code", None)
        issues.append(
            f"BROKER_ERROR_{code}"
            if type(code) is int and 0 <= code <= 99999
            else "BROKER_READ_FAILED"
        )
    finally:
        # Never bless unacknowledged/torn payload writes after interruption.
        save(refresh_files=False)
    coverage, gaps = {}, []
    for product, rows in rows_by_product.items():
        missing = sorted(set(sessions) - {r[0] for r in rows})
        coverage[product] = {
            "bars": len(rows),
            "expected_sessions": len(sessions),
            "start": rows[0][0] if rows else None,
            "end": rows[-1][0] if rows else None,
        }
        if missing:
            gaps.append(
                {"product": product, "code": "MISSING_SESSIONS", "sessions": missing}
            )
    receipt = {
        "schema": "competition.dataset_receipt.v2",
        "spec_hash": spec_hash(spec),
        "observed_at": observed.isoformat(),
        "status": "acquired" if not gaps and not issues else "partial",
        "coverage": coverage,
        "gaps": gaps,
        "issue_codes": issues,
        "resolved_contracts": state["resolved_contracts"],
        "calendar": calendar,
        "adjustment_evidence": {
            "price_basis": "split_adjusted",
            "corporate_actions": "not_verified",
            "out_of_overlap_revisions": "not_verified",
            "last_full_verification": state.get("refresh", {}).get(
                "last_full_verification"
            )
            if state.get("refresh")
            else observed.isoformat(),
        },
        "requests": state["requests"],
        "elapsed_seconds": state["elapsed_seconds"],
        "retained_payload_bytes": sum(f["bytes"] for f in state["files"]),
        "parent_manifest_sha256": None,
        "revisions": state.get("revisions", []),
        "accepted_research": False,
    }
    write_json(staging / "receipt.json", receipt)
    return receipt
