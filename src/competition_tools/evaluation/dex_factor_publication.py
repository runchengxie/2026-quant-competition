"""Strict, permission-gated public facts. Private metrics never enter readiness output."""

import math
import re
from datetime import datetime, timedelta, timezone

from competition_tools.datasets.dex_spec import safe_path, utc_hour
from competition_tools.datasets.dex_storage import read_json, verify_dex_manifest
from competition_tools.datasets.storage import digest
from competition_tools.team.factors import SIGNALS

RESTRICTIONS = [
    "fixed_current_selection",
    "bar_close_proxy_unverified",
    "gross_descriptive_forward_returns",
    "not_portfolio_pnl",
    "no_cost_or_execution_model",
    "no_out_of_sample_or_significance_claim",
]
HOUR = timedelta(hours=1)
# No real permission source has been human-reviewed. Populate only through a
# reviewed code change citing authoritative permission evidence, never a CLI receipt.
REVIEWED_PERMISSION_SOURCE_SHA256 = frozenset()


def keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("INVALID_PUBLIC_DEX_FACTS")


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError("INVALID_DEX_COUNT")


def number(value, *, correlation=False):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or (correlation and not -1 <= value <= 1)
    ):
        raise ValueError("INVALID_DEX_METRIC")


def metric(value, minimum):
    keys(value, {"value", "n", "reason"})
    integer(value["n"])
    if value["value"] is None:
        reasons = (
            {"INSUFFICIENT_OBSERVATIONS"}
            if value["n"] < minimum
            else {"CONSTANT_SIGNAL", "CONSTANT_TARGET"}
        )
        if value["reason"] not in reasons:
            raise ValueError("INVALID_DEX_NULL_REASON")
    else:
        number(value["value"], correlation=True)
        if value["n"] < minimum or value["reason"] is not None:
            raise ValueError("INVALID_DEX_NULL_REASON")


def validate_metrics(temporal, cross, assets):
    expected = {
        (a, s, h, m)
        for a in assets
        for s in SIGNALS
        for h in (6, 24)
        for m in ("all_valid", "non_overlapping")
    }
    seen = set()
    for record in temporal:
        keys(
            record,
            {"asset_id", "signal_id", "horizon", "sampling", "overall", "slices"},
        )
        identity = tuple(
            record[k] for k in ("asset_id", "signal_id", "horizon", "sampling")
        )
        if (
            identity not in expected
            or identity in seen
            or type(record["horizon"]) is not int
        ):
            raise ValueError("INVALID_DEX_METRIC_IDENTITY")
        seen.add(identity)
        metric(record["overall"], 30)
        if len(record["slices"]) != 3:
            raise ValueError("INVALID_DEX_SLICE_COUNT")
        for index, part in enumerate(record["slices"]):
            keys(part, {"index", "value", "n", "reason"})
            if type(part["index"]) is not int or part["index"] != index:
                raise ValueError("INVALID_DEX_SLICE_IDENTITY")
            metric({k: v for k, v in part.items() if k != "index"}, 20)
        if sum(p["n"] for p in record["slices"]) != record["overall"]["n"]:
            raise ValueError("DEX_DENOMINATOR_MISMATCH")
    if seen != expected:
        raise ValueError("MISSING_DEX_METRICS")
    expected_cross = {
        (s, h, m)
        for s in SIGNALS
        for h in (6, 24)
        for m in ("all_valid", "non_overlapping")
    }
    seen = set()
    for record in cross:
        keys(
            record,
            {
                "signal_id",
                "horizon",
                "sampling",
                "candidate_timestamps",
                "valid_timestamps",
                "ic_valid_timestamps",
                "ic_excluded_reasons",
                "ic_reason",
                "mean_rank_ic",
                "group_mean_forward_returns",
                "top_minus_bottom",
                "reason",
                "excluded_reasons",
            },
        )
        identity = tuple(record[k] for k in ("signal_id", "horizon", "sampling"))
        if identity not in expected_cross or identity in seen:
            raise ValueError("INVALID_DEX_METRIC_IDENTITY")
        seen.add(identity)
        for field in ("candidate_timestamps", "valid_timestamps"):
            integer(record[field])
        if set(record["excluded_reasons"]) - {
            "INSUFFICIENT_UNDERLYINGS",
            "INSUFFICIENT_GROUP_SIZE",
        }:
            raise ValueError("INVALID_DEX_NULL_REASON")
        for count in record["excluded_reasons"].values():
            integer(count)
        if (
            record["valid_timestamps"] + sum(record["excluded_reasons"].values())
            != record["candidate_timestamps"]
        ):
            raise ValueError("DEX_DENOMINATOR_MISMATCH")
        integer(record["ic_valid_timestamps"])
        if set(record["ic_excluded_reasons"]) - {"CONSTANT_SIGNAL", "CONSTANT_TARGET"}:
            raise ValueError("INVALID_DEX_NULL_REASON")
        for count in record["ic_excluded_reasons"].values():
            integer(count)
        if (
            record["ic_valid_timestamps"] + sum(record["ic_excluded_reasons"].values())
            != record["valid_timestamps"]
        ):
            raise ValueError("DEX_DENOMINATOR_MISMATCH")
        if record["ic_valid_timestamps"]:
            number(record["mean_rank_ic"], correlation=True)
            if record["ic_reason"] is not None:
                raise ValueError("INVALID_DEX_NULL_REASON")
        elif record["mean_rank_ic"] is not None or record["ic_reason"] != (
            record["reason"] or "CONSTANT_TARGET"
        ):
            raise ValueError("INVALID_DEX_NULL_REASON")
        if record["valid_timestamps"] == 0:
            if any(
                record[k] is not None
                for k in (
                    "mean_rank_ic",
                    "group_mean_forward_returns",
                    "top_minus_bottom",
                )
            ) or record["reason"] != (
                "INSUFFICIENT_UNDERLYINGS" if len(assets) < 9 else "NO_VALID_GROUPS"
            ):
                raise ValueError("INVALID_DEX_NULL_REASON")
        else:
            if (
                len(assets) < 9
                or record["reason"] is not None
                or len(record["group_mean_forward_returns"]) != 3
            ):
                raise ValueError("INVALID_DEX_GROUPS")
            for value in record["group_mean_forward_returns"]:
                number(value)
            number(record["top_minus_bottom"])
            groups = record["group_mean_forward_returns"]
            if not math.isclose(
                record["top_minus_bottom"],
                groups[2] - groups[0],
                abs_tol=1e-12,
                rel_tol=1e-12,
            ):
                raise ValueError("DEX_GROUP_SPREAD_MISMATCH")
    if seen != expected_cross:
        raise ValueError("MISSING_DEX_METRICS")


def validate_public_dex_factors(value):
    base = {
        "schema",
        "status",
        "as_of",
        "source_commit",
        "protocol_sha256",
        "manifest_sha256",
        "asset_ids",
        "range",
        "role",
        "blockers",
        "restrictions",
    }
    measured = value.get("status") == "measured" if isinstance(value, dict) else False
    keys(value, base | ({"coverage", "metrics", "permission"} if measured else set()))
    if (
        value["schema"] != "competition.public_dex_factors.v1"
        or value["status"] not in {"readiness_only", "measured"}
        or value["role"] != "retrospective"
        or value["restrictions"] != RESTRICTIONS
    ):
        raise ValueError("INVALID_PUBLIC_DEX_FACTS")
    if not re.fullmatch("[a-f0-9]{40}", value["source_commit"]):
        raise ValueError("INVALID_DEX_SOURCE")
    for key in ("protocol_sha256", "manifest_sha256"):
        if not re.fullmatch("[a-f0-9]{64}", value[key]):
            raise ValueError("INVALID_DEX_SOURCE")
    datetime.fromisoformat(value["as_of"].replace("Z", "+00:00"))
    assets = value["asset_ids"]
    if (
        not isinstance(assets, list)
        or not 1 <= len(assets) <= 10
        or len(set(assets)) != len(assets)
        or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", a) for a in assets)
    ):
        raise ValueError("INVALID_PUBLIC_DEX_ASSETS")
    keys(value["range"], {"start", "end"})
    if utc_hour(value["range"]["end"]) - utc_hour(value["range"]["start"]) != timedelta(
        days=90
    ):
        raise ValueError("INVALID_DEX_RANGE")
    if any(
        code
        not in {
            "PUBLICATION_PERMISSION_UNVERIFIED",
            "DEX_ACQUISITION_BLOCKED",
            "PARTIAL_DEX_COVERAGE",
        }
        for code in value["blockers"]
    ):
        raise ValueError("INVALID_PUBLIC_DEX_BLOCKER")
    if not measured:
        if "PUBLICATION_PERMISSION_UNVERIFIED" not in value["blockers"]:
            raise ValueError("INVALID_DEX_PERMISSION")
        return value
    keys(value["metrics"], {"time_series", "cross_sectional"})
    validate_metrics(
        value["metrics"]["time_series"], value["metrics"]["cross_sectional"], assets
    )
    validate_coverage(value["coverage"], assets)
    if not verified_permission(value["permission"]):
        raise ValueError("INVALID_DEX_PERMISSION")
    return value


def validate_coverage(coverage, assets):
    if len(coverage) != len(assets) or {r["asset_id"] for r in coverage} != set(assets):
        raise ValueError("DEX_COVERAGE_MISMATCH")
    for row in coverage:
        keys(row, {"asset_id", "expected_intervals", "observed_intervals"})
        integer(row["observed_intervals"])
        if (
            type(row["expected_intervals"]) is not int
            or row["expected_intervals"] != 2160
            or row["observed_intervals"] > 2160
        ):
            raise ValueError("DEX_COVERAGE_MISMATCH")


def verified_permission(value):
    fields = {
        "status",
        "scope",
        "source_url",
        "source_sha256",
        "checked_at",
        "conclusion",
    }
    try:
        return (
            isinstance(value, dict)
            and set(value) == fields
            and value["source_sha256"] in REVIEWED_PERMISSION_SOURCE_SHA256
            and value["status"] == "verified"
            and value["scope"] == "derived_statistics"
            and value["source_url"] == "https://dexpaprika.com/api/terms"
            and re.fullmatch("[a-f0-9]{64}", value["source_sha256"]) is not None
            and datetime.fromisoformat(
                value["checked_at"].replace("Z", "+00:00")
            ).tzinfo
            is not None
            and value["conclusion"] == "aggregate_publication_permitted"
        )
    except (ValueError, TypeError, KeyError):
        return False


def private_permission_verified(value):
    fields = {
        "status",
        "scope",
        "source_url",
        "source_sha256",
        "checked_at",
        "conclusion",
        "source_file",
        "supporting_clause",
    }
    try:
        if not isinstance(value, dict) or set(value) != fields:
            return False
        public = {
            k: v
            for k, v in value.items()
            if k not in {"source_file", "supporting_clause"}
        }
        if not verified_permission(public):
            return False
        source = safe_path(value["source_file"])
        clause = value["supporting_clause"]
        return (
            source.is_file()
            and source.stat().st_size <= 2 * 1024 * 1024
            and digest(source) == value["source_sha256"]
            and isinstance(clause, str)
            and 20 <= len(clause) <= 500
            and clause in source.read_text(encoding="utf-8")
        )
    except (ValueError, TypeError, KeyError, OSError, UnicodeError):
        return False


def verify_counts(protocol, manifest, result):
    root = safe_path(protocol["manifest_file"]).parent
    bars = {a["stable_id"]: {} for a in protocol["dataset"]["assets"]}
    for record in manifest["files"]:
        if record["role"] == "normalized":
            for row in read_json(safe_path(root / record["path"])):
                bars[row["asset_id"]][utc_hour(row["interval_end"])] = row
    actual = {a: len(v) for a, v in bars.items()}
    if any(
        actual[r["asset_id"]] != r["observed_intervals"] for r in result["coverage"]
    ):
        raise ValueError("DEX_COVERAGE_MISMATCH")
    start = utc_hour(protocol["dataset"]["start"])
    cross_times = {}
    for record in result["time_series"]:
        asset, signal, horizon, sampling = (
            record[k] for k in ("asset_id", "signal_id", "horizon", "sampling")
        )
        width = (
            25
            if signal == "momentum_24h"
            else 169
            if signal == "momentum_168h"
            else 192
        )
        grid = bars[asset]
        times = []
        for time in grid:
            offset = int((time - start).total_seconds() / 3600)
            if sampling == "non_overlapping" and offset % horizon:
                continue
            if not all(
                time + i * HOUR in grid for i in range(-(width - 1), horizon + 1)
            ):
                continue
            if (
                width == 192
                and sum(grid[time - i * HOUR]["volume"] for i in range(24, 192)) == 0
            ):
                continue
            times.append(offset)
        if record["overall"]["n"] != len(times) or any(
            part["n"] != sum(i * 720 <= t < (i + 1) * 720 for t in times)
            for i, part in enumerate(record["slices"])
        ):
            raise ValueError("DEX_DENOMINATOR_MISMATCH")
        cross_times.setdefault((signal, horizon, sampling), set()).update(times)
    for record in result["cross_sectional"]:
        if record["candidate_timestamps"] != len(
            cross_times[(record["signal_id"], record["horizon"], record["sampling"])]
        ):
            raise ValueError("DEX_DENOMINATOR_MISMATCH")


def build_public_dex_factors(protocol, manifest, result, permission):
    location = safe_path(protocol["manifest_file"])
    if not location.exists():
        location = safe_path(
            location.parent.with_name(location.parent.name + ".partial")
            / "manifest.json"
        )
    actual = verify_dex_manifest(location)
    copied_protocol = read_json(location.parent / "protocol.json")
    if (
        actual != manifest
        or copied_protocol != protocol
        or {k: manifest["spec"][k] for k in protocol["dataset"]} != protocol["dataset"]
    ):
        raise ValueError("DEX_FACTOR_SOURCE_MISMATCH")
    if result is None:
        if manifest["status"] != "blocked" or private_permission_verified(permission):
            raise ValueError("DEX_FACTOR_RESULT_REQUIRED")
        return validate_public_dex_factors(
            dict(
                schema="competition.public_dex_factors.v1",
                status="readiness_only",
                as_of=datetime.now(timezone.utc).isoformat(),
                source_commit=protocol["source_commit"],
                protocol_sha256=manifest["protocol_sha256"],
                manifest_sha256=digest(location),
                asset_ids=[a["stable_id"] for a in protocol["dataset"]["assets"]],
                range={k: protocol["dataset"][k] for k in ("start", "end")},
                role="retrospective",
                blockers=[
                    "PUBLICATION_PERMISSION_UNVERIFIED",
                    "DEX_ACQUISITION_BLOCKED",
                ],
                restrictions=RESTRICTIONS,
            )
        )
    keys(
        result,
        {
            "schema",
            "status",
            "dataset",
            "source_commit",
            "protocol_sha256",
            "manifest_sha256",
            "input_hashes",
            "source_files",
            "role",
            "coverage",
            "time_series",
            "cross_sectional",
            "restrictions",
        },
    )
    actual = verify_dex_manifest(safe_path(protocol["manifest_file"]))
    if (
        actual != manifest
        or read_json(safe_path(protocol["manifest_file"]).parent / "protocol.json")
        != protocol
        or result["schema"] != "competition.dex_factor_result.v1"
        or result["status"] != "completed"
        or result["dataset"] != protocol["dataset"]
        or result["source_commit"] != protocol["source_commit"]
        or result["source_files"] != protocol["source_files"]
        or result["protocol_sha256"] != manifest["protocol_sha256"]
        or result["manifest_sha256"] != digest(safe_path(protocol["manifest_file"]))
        or result["input_hashes"] != {r["path"]: r["sha256"] for r in manifest["files"]}
        or result["role"] != "retrospective"
        or result["restrictions"] != RESTRICTIONS
    ):
        raise ValueError("DEX_FACTOR_SOURCE_MISMATCH")
    assets = [a["stable_id"] for a in protocol["dataset"]["assets"]]
    validate_metrics(result["time_series"], result["cross_sectional"], assets)
    validate_coverage(result["coverage"], assets)
    verify_counts(protocol, manifest, result)
    if (
        verify_dex_manifest(location) != actual
        or digest(location) != result["manifest_sha256"]
    ):
        raise ValueError("DEX_FACTOR_SOURCE_MISMATCH")
    allowed = private_permission_verified(permission)
    blockers = [] if allowed else ["PUBLICATION_PERMISSION_UNVERIFIED"]
    if manifest["status"] == "blocked":
        blockers.append("DEX_ACQUISITION_BLOCKED")
    elif manifest["status"] == "partial":
        blockers.append("PARTIAL_DEX_COVERAGE")
    value = dict(
        schema="competition.public_dex_factors.v1",
        status="measured" if allowed else "readiness_only",
        as_of=datetime.now(timezone.utc).isoformat(),
        source_commit=protocol["source_commit"],
        protocol_sha256=result["protocol_sha256"],
        manifest_sha256=result["manifest_sha256"],
        asset_ids=assets,
        range={k: protocol["dataset"][k] for k in ("start", "end")},
        role="retrospective",
        blockers=blockers,
        restrictions=RESTRICTIONS,
    )
    if allowed:
        value.update(
            coverage=result["coverage"],
            metrics={k: result[k] for k in ("time_series", "cross_sectional")},
            permission={
                k: v
                for k, v in permission.items()
                if k not in {"source_file", "supporting_clause"}
            },
        )
    return validate_public_dex_factors(value)
