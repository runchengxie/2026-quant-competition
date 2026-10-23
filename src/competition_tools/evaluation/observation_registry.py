"""Immutable manual observation protocols. Freezing does not start collection."""

import math
import os
import subprocess
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ..datasets.daily_storage import safe_path
from ..datasets.storage import digest, write_json
from .ablation_source import verify_source_snapshot
from .controls.catalog import COSTS
from .controls.contracts import read_json
from .controls.source import snapshot_source
from .study_identity import canonical_hash, source_hash, tree_hash
from .ablation_runner import _verify_period_metrics
from ..team.processes import child_environment, interpreter, run_child

CANDIDATES = {
    "US": ["mom20_monthly", "mom20_monthly_buffer20", "ew_monthly"],
    "crypto": ["trend200_vol40_strict", "ew_trend_gross_matched", "ew_legacy"],
}
OWNER = "competition.observation_registry.v1"
RULES = dict(
    new_dates_per_import=512,
    seconds_per_import=3600,
    stop_conditions=[
        "unknown_availability",
        "missing_session",
        "changed_source",
        "changed_account_prefix",
        "budget_exhausted",
    ],
    timestamp_proof="local_hash_chain_only",
)
TRUSTED_AVAILABILITY_EVIDENCE: frozenset[str] = frozenset()
TEMPLATE_KEYS = set(
    "schema synthetic candidates costs warmup source_identity known_cutoff initial_nav valuation zero_volatility execution_authorized".split()
)


def utc_time(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("AWARE_OBSERVATION_TIME_REQUIRED")
    return value.astimezone(timezone.utc)


def _bars(value):
    if not isinstance(value, dict) or set(value) != {"dates", "close"}:
        raise ValueError("INVALID_OBSERVATION_BARS")
    dates, closes = value["dates"], value["close"]
    if (
        not isinstance(dates, list)
        or dates != sorted(set(dates))
        or not dates
        or not isinstance(closes, dict)
        or not closes
    ):
        raise ValueError("INVALID_OBSERVATION_GRID")
    for day in dates:
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
            raise ValueError("INVALID_OBSERVATION_DATE")
    for product, prices in closes.items():
        if (
            not isinstance(product, str)
            or not product
            or not isinstance(prices, list)
            or len(prices) != len(dates)
            or any(
                type(v) not in (int, float) or not math.isfinite(v) or v <= 0
                for v in prices
            )
        ):
            raise ValueError("INVALID_OBSERVATION_PRICES")
    return value


def _warmups(protocol):
    if not isinstance(protocol["warmup"], dict) or set(protocol["warmup"]) != {
        "US",
        "crypto",
    }:
        raise ValueError("INVALID_OBSERVATION_WARMUP")
    result = {}
    for market, record in protocol["warmup"].items():
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise ValueError("INVALID_OBSERVATION_WARMUP")
        path = safe_path(Path(record["path"]))
        if digest(path) != record["sha256"]:
            raise ValueError("OBSERVATION_WARMUP_CHANGED")
        result[market] = _bars(read_json(path))
        if (
            len(result[market]["dates"]) != 252
            or result[market]["dates"][-1]
            > utc_time(protocol["known_cutoff"]).date().isoformat()
        ):
            raise ValueError("INVALID_OBSERVATION_WARMUP_LENGTH_OR_CUTOFF")
        dates = result[market]["dates"]
        first, last = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
        if protocol["synthetic"] or market == "crypto":
            expected = [
                (first + timedelta(days=i)).isoformat()
                for i in range((last - first).days + 1)
            ]
        else:
            from ..datasets.session_calendar import completed_sessions

            expected = completed_sessions(
                "XNYS",
                first.isoformat(),
                last.isoformat(),
                as_of=utc_time(protocol["known_cutoff"]),
            )["sessions"]
        if dates != expected:
            raise ValueError("INVALID_OBSERVATION_WARMUP_GRID")
    return result


def _template(protocol, *, now, verify_current_source):
    if (
        not isinstance(protocol, dict)
        or set(protocol) != TEMPLATE_KEYS
        or protocol["schema"] != "competition.observation_protocol.v1"
        or type(protocol["synthetic"]) is not bool
        or canonical_hash(protocol["candidates"]) != canonical_hash(CANDIDATES)
        or canonical_hash(protocol["costs"]) != canonical_hash(COSTS)
        or type(protocol["initial_nav"]) not in (int, float)
        or protocol["initial_nav"] != 1
        or protocol["valuation"] != "lagged_close_proxy"
        or protocol["zero_volatility"] != "cash"
        or protocol["execution_authorized"] is not False
        or utc_time(protocol["known_cutoff"]) > utc_time(now)
    ):
        raise ValueError("INVALID_OBSERVATION_PROTOCOL")
    _warmups(protocol)
    identity = protocol["source_identity"]
    if not isinstance(identity, dict) or set(identity) != {
        "commit",
        "source_root",
        "source_sha256",
    }:
        raise ValueError("INVALID_OBSERVATION_SOURCE_IDENTITY")
    # Source is intentionally a Git checkout. External-output restrictions
    # apply to the retained snapshot destination, not its source checkout.
    if (
        verify_current_source
        and source_hash(Path(identity["source_root"])) != identity["source_sha256"]
    ):
        raise ValueError("OBSERVATION_SOURCE_CHANGED")


def freeze_observation(protocol: dict, registry_root: Path, *, now: datetime) -> dict:
    now = utc_time(now)
    _template(protocol, now=now, verify_current_source=True)
    root = safe_path(registry_root)
    if root.exists():
        raise FileExistsError("OBSERVATION_REGISTRY_EXISTS")
    root.mkdir(parents=True, exist_ok=False)
    snapshot = snapshot_source(
        Path(protocol["source_identity"]["source_root"]), root / "source"
    )
    if (
        snapshot["commit"] != protocol["source_identity"]["commit"]
        or snapshot["source_sha256"] != protocol["source_identity"]["source_sha256"]
    ):
        raise ValueError("OBSERVATION_SOURCE_CHANGED")
    value = dict(
        schema="competition.observation_protocol.v1",
        template=protocol,
        freeze_at=now.isoformat(),
        source_snapshot=snapshot,
        rules=RULES,
    )
    value["protocol_id"] = canonical_hash(value)
    write_json(root / "protocol.json", value)
    (root / "protocol.sha256").write_text(digest(root / "protocol.json"))
    (root / ".owner").write_text(OWNER)
    (root / "imports").mkdir()
    return inspect_observation(root)


def _protocol(root):
    root = safe_path(root)
    if (root / ".owner").read_text() != OWNER or digest(root / "protocol.json") != (
        root / "protocol.sha256"
    ).read_text().strip():
        raise ValueError("OBSERVATION_PROTOCOL_CHANGED")
    value = read_json(root / "protocol.json")
    if (
        set(value)
        != {
            "schema",
            "template",
            "freeze_at",
            "source_snapshot",
            "rules",
            "protocol_id",
        }
        or value["schema"] != "competition.observation_protocol.v1"
        or canonical_hash(value["rules"]) != canonical_hash(RULES)
        or canonical_hash({k: v for k, v in value.items() if k != "protocol_id"})
        != value["protocol_id"]
    ):
        raise ValueError("OBSERVATION_PROTOCOL_CHANGED")
    _template(
        value["template"], now=utc_time(value["freeze_at"]), verify_current_source=False
    )
    source = verify_source_snapshot(value["source_snapshot"])
    if (
        source["commit"] != value["template"]["source_identity"]["commit"]
        or source["source_sha256"]
        != value["template"]["source_identity"]["source_sha256"]
    ):
        raise ValueError("OBSERVATION_SOURCE_CHANGED")
    return value


def inspect_observation(registry_root: Path) -> dict:
    root = safe_path(registry_root)
    value = _protocol(root)
    history = _history(root, value)
    return _status(value, history)


def _status(value, history):
    latest, times = {}, []
    for receipt, manifest, _ in history:
        latest[receipt["market"]] = receipt["observations"]
        times.append(manifest["available_at"][0])
    return dict(
        schema="competition.observation_status.v1",
        protocol_id=value["protocol_id"],
        status="observing" if history else "awaiting_new_data",
        freeze_at=value["freeze_at"],
        first_eligible_observation_at=min(times) if times else None,
        observations=sum(latest.values()),
        evidence_tier="synthetic_valuation_only"
        if history and value["template"]["synthetic"]
        else "valuation_only"
        if history
        else "readiness_only",
        execution_authorized=False,
    )


def _review_availability(value, protocol, *, now=None):
    if value["synthetic"]:
        if (
            value["availability_basis"] != "synthetic"
            or value["availability_evidence"] is not None
        ):
            raise ValueError("OBSERVATION_AVAILABILITY_UNVERIFIED")
        return
    evidence = value["availability_evidence"]
    if (
        value["availability_basis"] != "verified"
        or not isinstance(evidence, dict)
        or set(evidence) != {"path", "sha256"}
        or evidence["sha256"] not in TRUSTED_AVAILABILITY_EVIDENCE
    ):
        raise ValueError("OBSERVATION_AVAILABILITY_UNVERIFIED")
    path = safe_path(Path(evidence["path"]))
    if digest(path) != evidence["sha256"]:
        raise ValueError("OBSERVATION_AVAILABILITY_UNVERIFIED")
    review = read_json(path)
    normalized = value | {
        "available_at": [utc_time(v).isoformat() for v in value["available_at"]]
    }
    expected = canonical_hash(
        {k: v for k, v in normalized.items() if k != "availability_evidence"}
    )
    if (
        set(review)
        != {
            "schema",
            "protocol_id",
            "market",
            "import_sha256",
            "decision",
            "reviewed_at",
        }
        or review["schema"] != "competition.observation_availability_review.v1"
        or review["decision"] != "verified"
        or review["protocol_id"] != protocol["protocol_id"]
        or value["protocol_id"] != protocol["protocol_id"]
        or review["market"] != value["market"]
        or review["import_sha256"] != expected
    ):
        raise ValueError("OBSERVATION_AVAILABILITY_REVIEW_CONTEXT")
    reviewed = utc_time(review["reviewed_at"])
    if reviewed < max(utc_time(v) for v in value["available_at"]) or (
        now is not None and reviewed > utc_time(now)
    ):
        raise ValueError("OBSERVATION_AVAILABILITY_REVIEW_TIME")


def _completed_bar_at(market, day, *, synthetic):
    if synthetic or market == "crypto":
        return datetime.combine(
            date.fromisoformat(day) + timedelta(days=1),
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
    from exchange_calendars import get_calendar

    parsed = date.fromisoformat(day)
    calendar = get_calendar(
        "XNYS",
        start=(parsed - timedelta(days=7)).isoformat(),
        end=(parsed + timedelta(days=7)).isoformat(),
    )
    return utc_time(calendar.session_close(day).to_pydatetime())


def _normalize_import(value, protocol, *, now):
    keys = {
        "schema",
        "protocol_id",
        "market",
        "synthetic",
        "price_basis",
        "quote_currency",
        "availability_basis",
        "availability_evidence",
        "available_at",
        "bars",
    }
    if (
        not isinstance(value, dict)
        or set(value) != keys
        or value["schema"] != "competition.observation_import.v1"
        or value["protocol_id"] != protocol["protocol_id"]
        or value["market"] not in CANDIDATES
        or type(value["synthetic"]) is not bool
        or value["synthetic"] != protocol["template"]["synthetic"]
    ):
        raise ValueError("INVALID_OBSERVATION_IMPORT")
    market = value["market"]
    if value["price_basis"] != (
        "raw" if market == "crypto" else "split_adjusted"
    ) or value["quote_currency"] != ("USDT" if market == "crypto" else "USD"):
        raise ValueError("OBSERVATION_PRICE_CONTRACT_MISMATCH")
    bars = _bars(value["bars"])
    warmup = _warmups(protocol["template"])[market]
    if (
        len(bars["dates"]) < 253
        or bars["dates"][:252] != warmup["dates"]
        or set(bars["close"]) != set(warmup["close"])
        or any(bars["close"][p][:252] != warmup["close"][p] for p in warmup["close"])
    ):
        raise ValueError("OBSERVATION_WARMUP_OR_BUDGET_MISMATCH")
    scored = bars["dates"][252:]
    if not isinstance(value["available_at"], list) or len(value["available_at"]) != len(
        scored
    ):
        raise ValueError("INVALID_OBSERVATION_AVAILABILITY")
    available = [utc_time(v) for v in value["available_at"]]
    cutoff = max(
        utc_time(protocol["freeze_at"]), utc_time(protocol["template"]["known_cutoff"])
    )
    for day, timestamp in zip(scored, available, strict=True):
        if (
            timestamp <= cutoff
            or timestamp > utc_time(now)
            or timestamp < _completed_bar_at(market, day, synthetic=value["synthetic"])
            or day <= utc_time(protocol["template"]["known_cutoff"]).date().isoformat()
        ):
            raise ValueError("BACKDATED_OR_UNAVAILABLE_OBSERVATION")
    if available != sorted(available):
        raise ValueError("OUT_OF_ORDER_OBSERVATION_AVAILABILITY")
    _review_availability(value, protocol, now=now)
    first = date.fromisoformat(bars["dates"][251]) + timedelta(days=1)
    last = date.fromisoformat(scored[-1])
    if market == "crypto" or value["synthetic"]:
        expected = [
            (first + timedelta(days=i)).isoformat()
            for i in range((last - first).days + 1)
        ]
    else:
        from ..datasets.session_calendar import completed_sessions

        expected = completed_sessions(
            "XNYS", first.isoformat(), last.isoformat(), as_of=utc_time(now)
        )["sessions"]
    if scored != expected:
        raise ValueError("MISSING_OR_DUPLICATE_OBSERVATION_SESSION")
    return value | {"available_at": [v.isoformat() for v in available]}


def _verify_replay(request, result, request_hash):
    if (
        set(result)
        != {
            "schema",
            "protocol_id",
            "request_sha256",
            "expected_leaf_sha256",
            "market",
            "results",
        }
        or result["schema"] != "competition.observation_replay_result.v1"
        or result["request_sha256"] != request_hash
        or any(
            result[k] != request[k]
            for k in ("protocol_id", "expected_leaf_sha256", "market")
        )
    ):
        raise ValueError("INVALID_OBSERVATION_REPLAY_RESULT")
    market = request["market"]
    expected = {(arm, fee) for arm in CANDIDATES[market] for fee in COSTS[market]}
    seen = set()
    if not isinstance(result["results"], list) or len(result["results"]) != len(
        expected
    ):
        raise ValueError("INCOMPLETE_OBSERVATION_REPLAY")
    for row in result["results"]:
        if (
            set(row) != {"arm_id", "fee_bps", "output"}
            or type(row["fee_bps"]) is not int
            or (row["arm_id"], row["fee_bps"]) not in expected
            or (row["arm_id"], row["fee_bps"]) in seen
        ):
            raise ValueError("INVALID_OBSERVATION_REPLAY_POLICY")
        seen.add((row["arm_id"], row["fee_bps"]))
        output = row["output"]
        if set(output) != {"net", "gross", "metrics", "diagnostics"}:
            raise ValueError("INVALID_OBSERVATION_REPLAY_OUTPUT")
        for side in ("net", "gross"):
            account = output[side]
            if (
                set(account) != {"accounting_model", "quote_currency", "periods"}
                or account["accounting_model"] != "self_financing_daily.v1"
                or account["quote_currency"]
                != ("USDT" if market == "crypto" else "USD")
            ):
                raise ValueError("INVALID_OBSERVATION_ACCOUNT")
        job = dict(
            job_id=request["protocol_id"],
            market=market,
            fee_bps=row["fee_bps"],
            products=list(request["bars"]["close"]),
            dates=request["bars"]["dates"],
        )
        _verify_period_metrics(
            job,
            output,
            dict(
                schema="competition.daily_study_periods.v2",
                job_id=job["job_id"],
                net=output["net"]["periods"],
                gross=output["gross"]["periods"],
            ),
        )


def _request(protocol, manifest):
    project = "equity-lab" if manifest["market"] == "US" else "crypto-mm"
    return dict(
        schema="competition.observation_replay_request.v1",
        protocol_id=protocol["protocol_id"],
        market=manifest["market"],
        bars=manifest["bars"],
        score_start=manifest["bars"]["dates"][252],
        expected_leaf_sha256=tree_hash(
            Path(protocol["source_snapshot"]["source_root"])
            / "research"
            / project
            / "src"
        ),
    )


def _extends(old, new, before=None, after=None):
    n = len(old["bars"]["dates"])
    if (
        len(new["bars"]["dates"]) <= n
        or new["bars"]["dates"][:n] != old["bars"]["dates"]
        or new["available_at"][: n - 252] != old["available_at"]
        or any(
            new["bars"]["close"][p][:n] != values
            for p, values in old["bars"]["close"].items()
        )
    ):
        raise ValueError("CONFLICTING_OR_OUT_OF_ORDER_OBSERVATION")
    if before is not None:
        for old_row, new_row in zip(before["results"], after["results"], strict=True):
            if (old_row["arm_id"], old_row["fee_bps"]) != (
                new_row["arm_id"],
                new_row["fee_bps"],
            ):
                raise ValueError("OBSERVATION_REPLAY_POLICY_CHANGED")
            for side in ("net", "gross"):
                previous = old_row["output"][side]["periods"]
                if new_row["output"][side]["periods"][: len(previous)] != previous:
                    raise ValueError("OBSERVATION_ACCOUNT_PREFIX_CHANGED")


def _history(root, protocol):
    result, previous = [], None
    for index, directory in enumerate(sorted((root / "imports").iterdir()), 1):
        if directory.name != f"{index:06}" or not directory.is_dir():
            raise ValueError("UNKNOWN_OBSERVATION_RECEIPT")
        receipt = read_json(safe_path(directory / "receipt.json"))
        expected = {
            "schema",
            "protocol_id",
            "market",
            "observations",
            "previous_receipt_sha256",
            "import_id",
            "source_path",
            "source_sha256",
            "files",
            "receipt_sha256",
        }
        if (
            set(receipt) != expected
            or receipt["schema"] != "competition.observation_receipt.v1"
            or receipt["protocol_id"] != protocol["protocol_id"]
            or receipt["previous_receipt_sha256"] != previous
            or canonical_hash(
                {k: v for k, v in receipt.items() if k != "receipt_sha256"}
            )
            != receipt["receipt_sha256"]
        ):
            raise ValueError("OBSERVATION_RECEIPT_CHANGED")
        if digest(safe_path(Path(receipt["source_path"]))) != receipt["source_sha256"]:
            raise ValueError("OBSERVATION_SOURCE_IMPORT_CHANGED")
        if {p.name for p in directory.iterdir()} != {
            "manifest.json",
            "request.json",
            "result.json",
            "receipt.json",
        }:
            raise ValueError("OBSERVATION_RECEIPT_ARTIFACT_CHANGED")
        files = [
            {"path": p.name, "sha256": digest(safe_path(p))}
            for p in sorted(directory.iterdir())
            if p.name != "receipt.json"
        ]
        if files != receipt["files"]:
            raise ValueError("OBSERVATION_RECEIPT_ARTIFACT_CHANGED")
        manifest = read_json(directory / "manifest.json")
        _review_availability(manifest, protocol)
        if (
            canonical_hash(manifest) != receipt["import_id"]
            or manifest["protocol_id"] != protocol["protocol_id"]
            or manifest["market"] != receipt["market"]
            or len(manifest["bars"]["dates"]) - 252 != receipt["observations"]
        ):
            raise ValueError("OBSERVATION_RECEIPT_IDENTITY_CHANGED")
        request = read_json(directory / "request.json")
        if canonical_hash(request) != canonical_hash(_request(protocol, manifest)):
            raise ValueError("OBSERVATION_REPLAY_REQUEST_CHANGED")
        replay = read_json(directory / "result.json")
        _verify_replay(request, replay, digest(directory / "request.json"))
        prior = next(
            (r for r in reversed(result) if r[0]["market"] == manifest["market"]), None
        )
        if prior:
            _extends(prior[1], manifest, prior[2], replay)
        result.append((receipt, manifest, replay))
        previous = receipt["receipt_sha256"]
    return result


def _run_replay(config, project, request_path, output_path, timeout):
    environment = child_environment(config)
    for key in list(environment):
        if key.upper().endswith(("API_KEY", "PASSWORD", "TOKEN")):
            environment.pop(key)
    module = (
        "equity_lab.study.observation_cli"
        if project == "equity-lab"
        else "crypto_mm.daily.observation_cli"
    )
    child = run_child(
        [
            str(interpreter(config, project)),
            "-m",
            module,
            "--request",
            str(request_path),
            "--output",
            str(output_path),
        ],
        environment=environment,
        timeout=timeout,
    )
    if child.returncode != 0:
        raise ValueError("OBSERVATION_CHILD_FAILED")


def append_observation(
    registry_root: Path, manifest_path: Path, *, config, now: datetime
) -> dict:
    start = time.monotonic()
    root = safe_path(registry_root)
    lock = root / ".lock"
    if lock.exists():
        raise ValueError("OBSERVATION_REGISTRY_BUSY")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        protocol = _protocol(root)
        history = _history(root, protocol)
        source = safe_path(manifest_path)
        source_hash_before = digest(source)
        manifest = _normalize_import(read_json(source), protocol, now=now)
        identity = canonical_hash(manifest)
        if any(r[0]["import_id"] == identity for r in history):
            return inspect_observation(root)
        prior = next(
            (r for r in reversed(history) if r[0]["market"] == manifest["market"]), None
        )
        if prior:
            _extends(prior[1], manifest)
        previous_count = prior[0]["observations"] if prior else 0
        if len(manifest["bars"]["dates"]) - 252 - previous_count > 512:
            raise ValueError("OBSERVATION_IMPORT_DATE_BUDGET")
        attempts = root / "attempts"
        attempts.mkdir(exist_ok=True)
        # Presentation/provenance edits must not reset an unchanged calculation.
        calculation_id = canonical_hash(
            {k: manifest[k] for k in ("protocol_id", "market", "bars")}
        )
        attempt = safe_path(attempts / calculation_id)
        if attempt.exists():
            raise ValueError("OBSERVATION_SPEND_UNKNOWN_OR_ALREADY_ATTEMPTED")
        attempt.mkdir()
        write_json(attempt / "attempt.json", dict(status="started", import_id=identity))
        project = "equity-lab" if manifest["market"] == "US" else "crypto-mm"
        request = _request(protocol, manifest)
        write_json(attempt / "request.json", request)
        left = 3600 - (time.monotonic() - start)
        if left <= 0:
            raise ValueError("OBSERVATION_TIME_BUDGET")
        try:
            _run_replay(
                config, project, attempt / "request.json", attempt / "result.json", left
            )
        except subprocess.TimeoutExpired:
            raise ValueError("OBSERVATION_CHILD_TIMEOUT") from None
        replay = read_json(attempt / "result.json")
        _verify_replay(request, replay, digest(attempt / "request.json"))
        if prior:
            _extends(prior[1], manifest, prior[2], replay)
        if time.monotonic() - start >= 3600:
            raise ValueError("OBSERVATION_TIME_BUDGET")
        staging = attempt / "accepted"
        staging.mkdir()
        write_json(staging / "manifest.json", manifest)
        write_json(staging / "request.json", request)
        write_json(staging / "result.json", replay)
        receipt = dict(
            schema="competition.observation_receipt.v1",
            protocol_id=protocol["protocol_id"],
            market=manifest["market"],
            observations=len(manifest["bars"]["dates"]) - 252,
            previous_receipt_sha256=history[-1][0]["receipt_sha256"]
            if history
            else None,
            import_id=identity,
            source_path=str(source),
            source_sha256=source_hash_before,
            files=[
                dict(path=p.name, sha256=digest(p)) for p in sorted(staging.iterdir())
            ],
        )
        receipt["receipt_sha256"] = canonical_hash(receipt)
        write_json(staging / "receipt.json", receipt)
        write_json(
            attempt / "attempt.json",
            dict(
                status="prepared",
                import_id=identity,
                elapsed_seconds=time.monotonic() - start,
            ),
        )
        if (
            digest(source) != source_hash_before
            or _protocol(root)["protocol_id"] != protocol["protocol_id"]
            or _history(root, protocol) != history
        ):
            raise ValueError("OBSERVATION_INPUT_CHANGED_DURING_REPLAY")
        if time.monotonic() - start >= 3600:
            raise ValueError("OBSERVATION_TIME_BUDGET")
        staging.rename(safe_path(root / "imports" / f"{len(history) + 1:06}"))
        # All expensive reads and validations precede acceptance and its deadline.
        return _status(protocol, history + [(receipt, manifest, replay)])
    finally:
        os.close(fd)
        lock.unlink()
