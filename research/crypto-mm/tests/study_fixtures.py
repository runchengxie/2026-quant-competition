"""Synthetic file-contract fixtures, never market observations."""

import csv
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def create_job(root, *, crypto=False, partial=False):
    root.mkdir(parents=True)
    dataset = root / "dataset"
    (dataset / "normalized").mkdir(parents=True)
    (dataset / ".dataset-owner").write_text(
        "competition.dataset.v1" if crypto else "competition.dataset.v2"
    )
    market, currency, project = (
        ("crypto", "USDT", "crypto-mm") if crypto else ("US", "USD", "equity-lab")
    )
    count = 342 if crypto else 315
    products = ["BTCUSDT", "ETHUSDT"] if crypto else ["A", "B"]
    benchmark = "equal_weight" if crypto else "SPY"
    dates = [(date(2023, 1, 1) + timedelta(days=i)).isoformat() for i in range(count)]
    files = []
    for product in products + ([] if crypto else [benchmark]):
        path = dataset / "normalized" / (product + ".csv")
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["date", "open", "high", "low", "close", "volume"])
            writer.writerows([[d, 100, 100, 100, 100, 1] for d in dates])
        files.append(
            {
                "path": "normalized/" + path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
        )
    spec = {
        "schema": "competition.dataset_spec.v1"
        if crypto
        else "competition.dataset_spec.v2",
        "dataset_id": "synthetic-contract",
        "version": "v1",
        "source": "binance_spot" if crypto else "ibkr_daily",
        "market": market,
        "quote_currency": currency,
        "products": products,
        "start": dates[0],
        "end": dates[-1],
        "timezone": "UTC" if crypto else "America/New_York",
        "calendar": "365" if crypto else "XNYS",
        "price_basis": "raw" if crypto else "split_adjusted",
        "universe_status": "fixed_current",
        "budget": {"requests": 20, "bytes": 1000000, "seconds": 60},
    }
    if not crypto:
        spec.update(
            benchmark=benchmark,
            contracts=[
                {
                    "product": p,
                    "symbol": p,
                    "exchange": "SMART",
                    "currency": "USD",
                    "role": "benchmark" if p == benchmark else "stock",
                }
                for p in products + [benchmark]
            ],
        )
    status = "partial" if partial else "acquired"
    receipt = {
        "schema": "competition.dataset_receipt.v2",
        "spec_hash": "c" * 64,
        "observed_at": "2026-01-01T00:00:00+00:00",
        "status": status,
        "coverage": {
            p: {
                "bars": count,
                "expected_sessions": count,
                "start": dates[0],
                "end": dates[-1],
            }
            for p in products + ([] if crypto else [benchmark])
        },
        "gaps": [],
        "issue_codes": [],
        "resolved_contracts": {},
        "calendar": {
            "sessions": dates,
            "calendar_name": "XNYS",
            "package_version": "synthetic",
            "schedule_sha256": "d" * 64,
            "latest_completed_session": dates[-1],
        },
        "adjustment_evidence": {
            "price_basis": "split_adjusted",
            "corporate_actions": "not_verified",
            "out_of_overlap_revisions": "not_verified",
            "last_full_verification": "2026-01-01T00:00:00+00:00",
        },
        "requests": 0,
        "elapsed_seconds": 0,
        "retained_payload_bytes": sum(f["bytes"] for f in files),
        "parent_manifest_sha256": None,
        "revisions": [],
        "accepted_research": False,
    }
    (dataset / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    manifest = {
        "schema": "competition.dataset_manifest.v1"
        if crypto
        else "competition.dataset_manifest.v2",
        "dataset_id": "synthetic-contract",
        "version": "v1",
        "spec_hash": "c" * 64,
        "spec": spec,
        "receipt": receipt,
        "observed_at": receipt["observed_at"],
        "status": status,
        "coverage": receipt["coverage"],
        "gaps": [],
        "files": files,
        "parent_manifest_sha256": None,
        "accepted_research": False,
    }
    manifest_path = dataset / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    src = Path(__file__).resolve().parents[1] / "src"
    leaf_sha = canonical_hash(
        [
            (p.relative_to(src).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(src.rglob("*.py"))
        ]
    )
    fold = {
        "warmup_start": dates[0],
        "start": dates[252],
        "end": dates[-1],
        "warmup_periods": 252,
        "scoring_periods": count - 252,
    }
    job = {
        "schema": "competition.daily_study_job.v1",
        "market": market,
        "project": project,
        "status": "planned",
        "manifest": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "input_files": files,
        "input_slice": {
            "schema": "competition.study_input_slice.v1",
            "parent_sha256": manifest_sha,
            "parent_status": status,
            "products": products,
            "start": dates[0],
            "end": dates[-1],
            "files": files,
            "selection": "fixed_current_from_2023",
            "accepted_research": False,
        },
        "products": products,
        "benchmark": benchmark,
        "quote_currency": currency,
        "strategy": "equal_weight",
        "parameters": {},
        "fee_bps": 10 if crypto else 20,
        "fold": fold,
        "dates": dates,
        "accounting_model": "self_financing_daily.v1",
        "execution_assumption": "lagged_close_proxy",
        "independent_fold_start": True,
        "max_positions": 20 if crypto else 10,
        "max_gross_exposure": 1,
        "signal_lag_periods": 1,
        "expected_leaf_sha256": leaf_sha,
        "accepted_research": False,
        "code_commit": "b" * 40,
        "plan_sha256": "a" * 64,
    }
    job["job_id"] = canonical_hash(
        {
            k: job[k]
            for k in ("market", "manifest_sha256", "strategy", "fold", "fee_bps")
        }
    )
    path = root / "job.json"
    path.write_text(json.dumps(job), encoding="utf-8")
    return path, job
