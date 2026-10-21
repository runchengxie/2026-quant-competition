"""Verified normalized portfolio curves, without raw prices or positions."""

import argparse
import json
import math
from datetime import date
from pathlib import Path

from competition_tools.datasets.daily_storage import safe_path
from competition_tools.datasets.storage import digest, write_json
from .study_publication import project_study, validate_public_study

POINT_KEYS = {"date", "net_nav", "gross_nav", "drawdown"}
SERIES_KEYS = {"job_id", "market", "quote_currency", "strategy", "cost_bps", "points"}
REFERENCE_REASON = "PRICE_LINKED_REFERENCE_SERIES_NOT_PUBLISHED"


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def build_points(job: dict, result: dict, periods: dict) -> list[dict]:
    try:
        dates = job["dates"]
        net, gross = periods["net"], periods["gross"]
        if (
            periods["schema"] != "competition.daily_study_periods.v1"
            or periods["job_id"] != job["job_id"]
            or len(dates) != 252 + job["fold"]["scoring_periods"]
            or dates != sorted(set(dates))
            or any(date.fromisoformat(d).isoformat() != d for d in dates)
        ):
            raise ValueError
        if len(net) != len(dates) - 252 or len(gross) != len(net):
            raise ValueError
        points = [dict(date=dates[251], net_nav=1.0, gross_nav=1.0, drawdown=0.0)]
        peak = 1.0
        for expected, n, g in zip(dates[252:], net, gross):
            if (
                n["date"] != expected
                or g["date"] != expected
                or any(not _number(p["equity"]) or p["equity"] <= 0 for p in (n, g))
            ):
                raise ValueError
            peak = max(peak, n["equity"])
            points.append(
                dict(
                    date=expected,
                    net_nav=n["equity"],
                    gross_nav=g["equity"],
                    drawdown=1 - n["equity"] / peak,
                )
            )
        m = result["metrics"]
        for actual, expected in [
            (points[-1]["net_nav"] - 1, m["net_return"]),
            (points[-1]["gross_nav"] - 1, m["gross_return"]),
            (max(p["drawdown"] for p in points), m["max_drawdown"]),
        ]:
            if not _number(expected) or not math.isclose(
                actual, expected, rel_tol=0, abs_tol=1e-10
            ):
                raise ValueError
        return points
    except (KeyError, TypeError, ValueError, IndexError):
        raise ValueError("INVALID_STUDY_SERIES") from None


def validate_public_series(value: dict, study: dict) -> dict:
    validate_public_study(study)
    try:
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "schema",
                "plan_sha256",
                "code_commit",
                "as_of",
                "series",
                "unavailable",
            }
            or value["schema"] != "competition.public_study_series.v1"
            or any(
                value[k] != study[k] for k in ("plan_sha256", "code_commit", "as_of")
            )
            or not isinstance(value["series"], list)
            or not isinstance(value["unavailable"], list)
        ):
            raise ValueError
        known = {r["job_id"]: r for r in study["results"]}
        seen = set()
        for curve in value["series"]:
            if (
                not isinstance(curve, dict)
                or set(curve) != SERIES_KEYS
                or not isinstance(curve["job_id"], str)
                or curve["job_id"] in seen
            ):
                raise ValueError
            row = known[curve["job_id"]]
            if (
                row["status"] != "completed"
                or row["strategy"] == "benchmark_buy_hold"
                or any(
                    curve[k] != row[k] for k in ("market", "quote_currency", "strategy")
                )
                or type(curve["cost_bps"]) is not int
                or curve["cost_bps"] != row["cost_bps"]
            ):
                raise ValueError
            points = curve["points"]
            if not isinstance(points, list) or len(points) != row["sessions"] + 1:
                raise ValueError
            peak = 1.0
            previous = None
            for i, point in enumerate(points):
                if (
                    not isinstance(point, dict)
                    or set(point) != POINT_KEYS
                    or not isinstance(point["date"], str)
                    or date.fromisoformat(point["date"]).isoformat() != point["date"]
                    or (previous is not None and point["date"] <= previous)
                    or any(
                        not _number(point[k])
                        for k in ("net_nav", "gross_nav", "drawdown")
                    )
                    or min(point["net_nav"], point["gross_nav"]) <= 0
                ):
                    raise ValueError
                if i == 0 and (
                    point["date"] >= row["start"]
                    or point["net_nav"] != 1
                    or point["gross_nav"] != 1
                    or point["drawdown"] != 0
                ):
                    raise ValueError
                peak = max(peak, point["net_nav"])
                if not math.isclose(
                    point["drawdown"],
                    1 - point["net_nav"] / peak,
                    rel_tol=0,
                    abs_tol=1e-10,
                ):
                    raise ValueError
                previous = point["date"]
            if (
                points[1]["date"] != row["start"]
                or points[-1]["date"] != row["end"]
                or any(
                    not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-10)
                    for actual, expected in (
                        (points[-1]["net_nav"] - 1, row["net_return"]),
                        (points[-1]["gross_nav"] - 1, row["gross_return"]),
                        (max(p["drawdown"] for p in points), row["max_drawdown"]),
                    )
                )
            ):
                raise ValueError
            seen.add(curve["job_id"])
        for blocked in value["unavailable"]:
            if (
                not isinstance(blocked, dict)
                or set(blocked) != {"job_id", "reason_code"}
                or not isinstance(blocked["job_id"], str)
                or blocked["job_id"] in seen
            ):
                raise ValueError
            row = known[blocked["job_id"]]
            expected = (
                REFERENCE_REASON
                if row["status"] == "completed"
                and row["strategy"] == "benchmark_buy_hold"
                else row["reason_code"]
            )
            if expected is None or blocked["reason_code"] != expected:
                raise ValueError
            seen.add(blocked["job_id"])
        if seen != set(known):
            raise ValueError
        return value
    except (KeyError, TypeError, ValueError, IndexError):
        raise ValueError("INVALID_PUBLIC_STUDY_SERIES") from None


def project_series(aggregate: dict) -> dict:
    study = project_study(aggregate)
    plan = json.loads(
        safe_path(Path(aggregate["plan_path"])).read_text(encoding="utf-8")
    )
    jobs = {j["job_id"]: j for j in plan["jobs"]}
    records = {r["job_id"]: r for r in aggregate["jobs"]}
    curves, unavailable = [], []
    for row in study["results"]:
        if row["status"] != "completed" or row["strategy"] == "benchmark_buy_hold":
            unavailable.append(
                dict(
                    job_id=row["job_id"],
                    reason_code=REFERENCE_REASON
                    if row["status"] == "completed"
                    else row["reason_code"],
                )
            )
            continue
        record = records[row["job_id"]]
        result_path = safe_path(Path(record["result_path"]))
        result = json.loads(result_path.read_text(encoding="utf-8"))
        artifact = result["artifacts"][0]
        path = safe_path(result_path.parent / "periods.json")
        if (
            digest(result_path) != row["result_sha256"]
            or digest(path) != artifact["sha256"]
            or path.stat().st_size != artifact["bytes"]
        ):
            raise ValueError("STUDY_SERIES_INPUT_CHANGED")
        points = build_points(
            jobs[row["job_id"]], result, json.loads(path.read_text(encoding="utf-8"))
        )
        if digest(path) != artifact["sha256"]:
            raise ValueError("STUDY_SERIES_INPUT_CHANGED")
        curves.append(
            dict(
                job_id=row["job_id"],
                market=row["market"],
                quote_currency=row["quote_currency"],
                strategy=row["strategy"],
                cost_bps=row["cost_bps"],
                points=points,
            )
        )
    return validate_public_series(
        dict(
            schema="competition.public_study_series.v1",
            plan_sha256=study["plan_sha256"],
            code_commit=study["code_commit"],
            as_of=study["as_of"],
            series=curves,
            unavailable=unavailable,
        ),
        study,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = project_series(
        json.loads(safe_path(args.aggregate).read_text(encoding="utf-8"))
    )
    output = safe_path(args.output)
    if output.exists():
        raise ValueError("PUBLIC_SERIES_OUTPUT_EXISTS")
    write_json(output, value)


if __name__ == "__main__":
    main()
