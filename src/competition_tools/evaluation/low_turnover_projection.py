"""Project immutable research bundles into a closed aggregate-only candidate."""

import argparse
import csv
import json
from pathlib import Path

from ..datasets.daily_storage import safe_path
from ..datasets.security_evidence import audit_security_evidence
from .comparison_evidence import project_bundle, read_json
from .comparison_publication import (
    validate_public_comparison,
    REVIEWED_SHA256 as PARENT_SHA256,
)
from .low_turnover_evidence import load_observations, verify_holding_export
from .low_turnover_publication import validate_candidate
from .research_diagnostics import cost_threshold, crypto_attribution, match
from .run_record import verify_run
from .study_identity import canonical_hash


def _table(path):
    path = safe_path(path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("SECURITY_METADATA_LIMIT")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def saved_diagnostics(parent):
    parent = safe_path(parent)
    verified = project_bundle(parent)
    validate_public_comparison(verified)
    costs = []
    for row in verified["equity"]["accounts"]:
        if row["fee_bps"] != 0:
            continue
        result = {
            k: row[k]
            for k in (
                "window",
                "arm",
                "delay",
                "status",
                "valid_dates",
                "requested_dates",
            )
        }
        result.update(
            gross_return=None, break_even_one_way_bps=None, mean_daily_turnover=None
        )
        if row["status"] == "completed":
            account = read_json(
                parent
                / "equity"
                / f"{row['window']}-{row['arm']}-0-{row['delay']}.json"
            )
            diagnostic = cost_threshold(
                [period["net_return"] for period in account["periods"]]
            )
            match(diagnostic["gross_return"], row["metrics"]["net_return"])
            result.update(
                gross_return=diagnostic["gross_return"],
                break_even_one_way_bps=diagnostic["break_even_one_way_bps"],
                mean_daily_turnover=row["metrics"]["turnover"] / 20,
            )
            for fee in (20, 40):
                charged = next(
                    r
                    for r in verified["equity"]["accounts"]
                    if (r["window"], r["arm"], r["delay"], r["fee_bps"])
                    == (row["window"], row["arm"], row["delay"], fee)
                )
                expected = (1 + result["gross_return"]) * (
                    (1 - fee / 10000) / (1 + fee / 10000)
                ) ** 20 - 1
                match(charged["metrics"]["net_return"], expected)
        costs.append(result)
    attribution = []
    for row in verified["crypto"]["accounts"]:
        artifact = read_json(
            parent
            / "crypto"
            / f"{row['window']}-{row['arm']}-{row['fee_bps']}-{row['delay']}.json"
        )
        result = crypto_attribution(artifact["prices"], artifact["net"])
        match(result["net_return"], row["metrics"]["net_return"])
        attribution.append(
            {k: row[k] for k in ("window", "end", "arm", "fee_bps", "delay")}
            | {
                k: result[k]
                for k in (
                    "net_return",
                    "components",
                    "dates",
                    "mean_post_trade_exposure",
                    "down_market_dates",
                    "down_market_strategy_pnl",
                    "down_market_full_reference_pnl",
                )
            }
        )
    return dict(
        requested=24,
        completed=sum(r["status"] == "completed" for r in costs),
        accounts=costs,
    ), dict(currency="USDT", accounts=attribution)


def project_run(root):
    root = safe_path(root)
    result = verify_run(root)
    plan = read_json(root / "experiment-plan.json")
    if (
        result["status"] != "completed"
        or plan["parameters"].get("protocol")
        != "competition.low_turnover_research.20261025.v1"
    ):
        raise ValueError("INCOMPLETE_LOW_TURNOVER_RUN")
    inputs = {row["path"]: row["sha256"] for row in plan["inputs"]}
    lineage = read_json(root / "inputs/parent.json")
    if lineage["public_sha256"] != PARENT_SHA256:
        raise ValueError("CHANGED_PARENT_COMPARISON")
    parent_root = safe_path(Path(lineage["run_root"]))
    parent_result = verify_run(parent_root)
    if parent_result["result_sha256"] != lineage["result_sha256"]:
        raise ValueError("PARENT_COMPARISON_CHANGED")
    equity = verify_holding_export(root / "equity")
    producer = read_json(root / "equity/report.json")
    if (
        producer.get("input_sha256") != inputs["inputs/daily.parquet"]
        or producer.get("source_unchanged") is not True
    ):
        raise ValueError("HOLDING_INPUT_LINEAGE_CHANGED")
    costs, crypto = saved_diagnostics(parent_root)
    observations = load_observations(root / "equity")
    records = [
        dict(
            date=stamp,
            candidate_id=name,
            ticker=row["ticker"],
            open=row["open"],
            close=row["close"],
        )
        for (stamp, name), row in observations.items()
    ]
    master = _table(root / "inputs/security-master.csv")
    intervals = _table(root / "inputs/security-intervals.csv")
    events = _table(root / "inputs/action-seeds.csv")
    reviewed = read_json(root / "inputs/primary-reviews.json")
    if not isinstance(reviewed, list) or len(reviewed) > len(events):
        raise ValueError("INVALID_PRIMARY_REVIEW_SCOPE")
    identities = {
        (r["symbol"], r["event_date"], r["event_type"], r["source_url"]) for r in events
    }
    review_ids = []
    for row in reviewed:
        if (
            set(row)
            != {
                "symbol",
                "event_date",
                "event_type",
                "source_url",
                "reviewed_at",
                "scope",
            }
            or row["scope"] != "announcement_or_filing_only"
        ):
            raise ValueError("INVALID_PRIMARY_REVIEW_FIELDS")
        identity = tuple(
            row[k] for k in ("symbol", "event_date", "event_type", "source_url")
        )
        if identity not in identities or identity in review_ids:
            raise ValueError("PRIMARY_REVIEW_IDENTITY_CHANGED")
        review_ids.append(identity)
    security = audit_security_evidence(records, master, intervals, events)
    security["primary_announcements_reviewed"] = len(reviewed)
    value = dict(
        schema="competition.low_turnover_public.v1",
        retrospective=True,
        formal_performance_ready=False,
        scientific=dict(
            commit=plan["code"]["commit"],
            plan_sha256=plan["plan_sha256"],
            result_sha256=result["result_sha256"],
            daily_input_sha256=inputs["inputs/daily.parquet"],
            parent_comparison_sha256=PARENT_SHA256,
        ),
        equity=equity,
        cost_diagnostics=costs,
        crypto=crypto,
        security=security,
        observation=read_json(root / "inputs/observation.json"),
    )
    validate_candidate(value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = project_run(args.run_root)
    with safe_path(args.output).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(status="projected", retrospective=True, sha256=canonical_hash(result))
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
