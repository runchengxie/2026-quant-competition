"""Offline request inventories and per-market warmup review candidates."""

import csv
import copy
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ..datasets.binance_daily_acquisition import inspect_daily_extension
from ..datasets.daily_storage import safe_path, verify_daily_manifest
from ..datasets.quality import validate_bars
from ..datasets.session_calendar import completed_sessions
from ..datasets.storage import digest, spec_hash, verify_manifest, write_json
from .controls.catalog import COSTS
from .observation_registry import CANDIDATES, inspect_observation, utc_time

US_INSTRUMENTS = frozenset("AAPL MSFT AMZN GOOGL META NVDA JPM JNJ XOM PG SPY".split())


def us_refresh_inventory(
    instruments: list[str], parent_sessions: list[str], end: str, *, retained_bytes: int
) -> dict:
    if (
        set(instruments) != US_INSTRUMENTS
        or len(instruments) != 11
        or not parent_sessions
        or parent_sessions != sorted(set(parent_sessions))
        or not 0 <= retained_bytes <= 10 * 1024**2
        or end < parent_sessions[-1]
    ):
        raise ValueError("INVALID_US_REFRESH_INVENTORY")
    overlap = parent_sessions[-min(5, len(parent_sessions))]
    return dict(
        requests=[
            dict(
                product=p,
                kind=kind,
                start=overlap if kind == "history" else None,
                end=end if kind == "history" else None,
            )
            for p in instruments
            for kind in ("qualification", "history")
        ],
        overlap_start=overlap,
        parent_retained_bytes=retained_bytes,
        budget=dict(
            requests=22,
            historical_requests=11,
            bytes=10 * 1024**2,
            seconds=300,
            attempts_per_request=1,
        ),
        minimum_pacing_seconds=210,
        activation_required=True,
        gateway_activation=False,
        revisions_beyond_budget="blocked",
    )


def prepare_us_refresh(
    config, base_manifest: Path, end_at: datetime, output: Path
) -> dict:
    now = utc_time(end_at)
    parent = safe_path(base_manifest)
    base = verify_daily_manifest(parent)
    spec = base["spec"]
    if spec["market"] != "US" or base["status"] != "acquired":
        raise ValueError("COMPLETE_US_REFRESH_PARENT_REQUIRED")
    calendar = completed_sessions(
        "XNYS", spec["start"], now.date().isoformat(), as_of=now
    )
    value = us_refresh_inventory(
        spec["products"] + [spec["benchmark"]],
        base["receipt"]["calendar"]["sessions"],
        calendar["latest_completed_session"],
        retained_bytes=base["receipt"]["retained_payload_bytes"],
    )
    value.update(
        schema="competition.us_refresh_preparation.v1",
        parent_manifest=str(parent),
        parent_sha256=digest(parent),
        parent_start=spec["start"],
        parent_identity=spec,
        calendar=calendar,
        missing_sessions=[d for d in calendar["sessions"] if d > spec["end"]],
        status="ready_for_activation_review",
        accepted_research=False,
    )
    value["preparation_sha256"] = spec_hash(value)
    out = safe_path(output)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "us-refresh-plan.json", value)
    return value


def prepare_observation(
    config,
    manifest: Path,
    output: Path,
    *,
    parent_registry: Path,
    now: datetime | None = None,
) -> dict:
    now = utc_time(now or datetime.now(timezone.utc))
    path = safe_path(manifest)
    header = json.loads(path.read_text(encoding="utf-8-sig"))
    if header.get("schema") == "competition.daily_recovery_manifest.v1":
        from ..datasets.daily_recovery import inspect_recovery

        value = inspect_recovery(path)
        market, products = "crypto", sorted(value["coverage"])
        collected_at = value["receipt"]["collected_at"]
    elif header.get("schema") == "competition.binance_daily_manifest.v1":
        value = inspect_daily_extension(path)
        market, products = "crypto", sorted(value["coverage"])
        collected_at = value["receipt"]["collected_at"]
    else:
        value = verify_manifest(path)
        market = value["spec"]["market"]
        if market not in {"US", "crypto"}:
            raise ValueError("UNSUPPORTED_PREPARATION_MARKET")
        products = value["spec"]["products"]
        spec = value["spec"]
        expected = (
            ("ibkr_daily", "USD", "XNYS", "America/New_York", "split_adjusted")
            if market == "US"
            else ("binance_spot", "USDT", "365", "UTC", "raw")
        )
        if (
            tuple(
                spec[k]
                for k in (
                    "source",
                    "quote_currency",
                    "calendar",
                    "timezone",
                    "price_basis",
                )
            )
            != expected
        ):
            raise ValueError("INCOMPATIBLE_OBSERVATION_SOURCE")
        if market == "US" and (
            set(products) != US_INSTRUMENTS - {"SPY"} or spec["benchmark"] != "SPY"
        ):
            raise ValueError("INCOMPATIBLE_OBSERVATION_POOL")
        collected_at = value["observed_at"]
    parent = inspect_observation(parent_registry)
    tables = {}
    for product in products:
        with safe_path(path.parent / "normalized" / f"{product}.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            reader = csv.reader(stream)
            if next(reader, None) != ["date", "open", "high", "low", "close", "volume"]:
                raise ValueError("INVALID_WARMUP_HEADER")
            rows = list(reader)
        validate_bars(rows)
        tables[product] = {r[0]: float(r[4]) for r in rows}
    if not tables or any(not rows for rows in tables.values()):
        raise ValueError("EMPTY_WARMUP_INPUT")
    latest = min(max(rows) for rows in tables.values())
    if market == "crypto":
        start = date.fromisoformat(latest) - timedelta(days=251)
        dates = [(start + timedelta(days=i)).isoformat() for i in range(252)]
        completed = (now.date() - timedelta(days=1)).isoformat()
        next_day = (date.fromisoformat(latest) + timedelta(days=1)).isoformat()
    else:
        lower = (date.fromisoformat(latest) - timedelta(days=550)).isoformat()
        grid = completed_sessions(
            "XNYS",
            lower,
            (now.date() + timedelta(days=14)).isoformat(),
            as_of=now + timedelta(days=15),
        )["sessions"]
        dates = [d for d in grid if d <= latest][-252:]
        current = completed_sessions("XNYS", lower, now.date().isoformat(), as_of=now)
        completed = current["latest_completed_session"]
        next_day = next(d for d in grid if d > latest)
    issues = []
    if value.get("receipt", {}).get("revisions"):
        issues.append("REVISED_INPUT_REQUIRES_REVIEW")
    if len(dates) != 252 or any(
        any(d not in rows for d in dates) for rows in tables.values()
    ):
        issues.append("INCOMPLETE_WARMUP")
    if latest != completed:
        issues.append("STALE_OR_INCOMPLETE_MARKET_DATE")
    if utc_time(collected_at) > now:
        issues.append("FUTURE_COLLECTION_TIMESTAMP")
    old_protocol = json.loads(safe_path(parent_registry / "protocol.json").read_text())
    old_warmup = json.loads(
        safe_path(Path(old_protocol["template"]["warmup"][market]["path"])).read_text()
    )
    if latest <= old_warmup["dates"][-1]:
        issues.append("WARMUP_NOT_EXTENDED")
    out = safe_path(output)
    out.mkdir(parents=True, exist_ok=False)
    warmup = (
        dict(
            dates=dates,
            close={p: [rows[d] for d in dates] for p, rows in tables.items()},
        )
        if "INCOMPLETE_WARMUP" not in issues
        else None
    )
    warmup_record = None
    if warmup:
        write_json(out / "warmup.json", warmup)
        warmup_record = dict(
            path=str(out / "warmup.json"), sha256=digest(out / "warmup.json")
        )
    result = dict(
        schema="competition.observation_preparation.v1",
        market=market,
        status="blocked" if issues else "ready_for_freeze_review",
        issue_codes=issues,
        prepared_at=now.isoformat(),
        collected_at=collected_at,
        manifest=str(path),
        manifest_sha256=digest(path),
        parent_protocol_id=parent["protocol_id"],
        new_protocol_id=None,
        warmup=warmup_record,
        warmup_end=latest,
        next_eligible_date=next_day,
        candidates=list(CANDIDATES[market]),
        costs=list(COSTS[market]),
        observations=0,
        availability_review_required=True,
        execution_authorized=False,
    )
    write_json(out / "preparation.json", result)
    write_json(
        out / "relationship-candidate.json",
        dict(
            schema="competition.observation_relationship.v1",
            parent_protocol_id=parent["protocol_id"],
            new_protocol_id=None,
            preparation_sha256=digest(out / "preparation.json"),
            market=market,
            status="not_frozen",
        ),
    )
    return result


def freeze_prepared_market(
    config,
    preparation: Path,
    parent_registry: Path,
    registry_root: Path,
    *,
    now: datetime,
    source_root: Path | None = None,
) -> dict:
    """Freeze one eligible market without claiming the other has fresh inputs.

    v1 retains both candidate groups. Its inactive market keeps the parent
    warmup and cannot import intervening old bars through the cutoff gate.
    A separately prepared protocol is required for that market to start.
    """
    from .observation_registry import freeze_observation
    from .study_identity import source_identity

    now = utc_time(now)
    prepared_path = safe_path(preparation)
    prepared = json.loads(prepared_path.read_text())
    parent = inspect_observation(parent_registry)
    if (
        prepared["parent_protocol_id"] != parent["protocol_id"]
        or prepared["status"] != "ready_for_freeze_review"
        or digest(safe_path(Path(prepared["manifest"]))) != prepared["manifest_sha256"]
    ):
        raise ValueError("PREPARATION_NOT_READY_OR_CHANGED")
    root = safe_path(registry_root)
    if root.exists():
        raise FileExistsError("OBSERVATION_REGISTRY_EXISTS")
    refreshed = prepare_observation(
        config,
        Path(prepared["manifest"]),
        root.with_name(root.name + "-review"),
        parent_registry=parent_registry,
        now=now,
    )
    if refreshed["status"] != "ready_for_freeze_review":
        raise ValueError("STALE_OR_INCOMPLETE_PREPARATION")
    original = json.loads(safe_path(parent_registry / "protocol.json").read_text())
    template = copy.deepcopy(original["template"])
    market = refreshed["market"]
    template["warmup"][market] = refreshed["warmup"]
    ends = [
        json.loads(safe_path(Path(record["path"])).read_text())["dates"][-1]
        for record in template["warmup"].values()
    ]
    # known_cutoff is the inspected price-date boundary, not a fabricated
    # collection timestamp. Actual collection/preparation/freeze times persist.
    boundary = utc_time(max(ends) + "T23:59:59.999999+00:00")
    template["known_cutoff"] = min(now, boundary).isoformat()
    if (
        refreshed["next_eligible_date"]
        <= utc_time(template["known_cutoff"]).date().isoformat()
    ):
        raise ValueError("NO_UNSEEN_NEXT_MARKET_DATE")
    template["source_identity"] = source_identity(
        source_root or Path(__file__).resolve().parents[3]
    )
    status = freeze_observation(template, root, now=now)
    write_json(
        root / "relationship.json",
        dict(
            schema="competition.observation_relationship.v1",
            parent_protocol_id=parent["protocol_id"],
            new_protocol_id=status["protocol_id"],
            preparation_sha256=digest(
                root.with_name(root.name + "-review") / "preparation.json"
            ),
            market=market,
            status="frozen",
        ),
    )
    return status
