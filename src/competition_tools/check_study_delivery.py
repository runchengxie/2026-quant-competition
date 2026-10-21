"""Exercise real installed study CLIs with explicitly synthetic flat-price inputs."""

import argparse
import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path

from .datasets.storage import digest, write_json, write_manifest
from .datasets.daily_storage import payload_files
from .evaluation.study_identity import source_identity
from .evaluation.study_plan import COSTS, freeze_study
from .evaluation.study_runner import run_study
from .team.config import load_config
from .team.paths import validate_external


def synthetic_manifest(root: Path, *, crypto: bool) -> Path:
    """Create no-network contract vectors, not exchange-session observations."""
    root.mkdir(parents=True, exist_ok=False)
    (root / "normalized").mkdir()
    (root / ".dataset-owner").write_text(
        "competition.dataset.v1" if crypto else "competition.dataset.v2"
    )
    count = 342 if crypto else 315
    dates = [(date(2023, 1, 1) + timedelta(days=i)).isoformat() for i in range(count)]
    products = ["BTCUSDT", "ETHUSDT"] if crypto else ["A", "B"]
    selected = products if crypto else products + ["SPY"]
    for product in selected:
        with (root / "normalized" / (product + ".csv")).open(
            "w", newline="", encoding="utf-8"
        ) as stream:
            writer = csv.writer(stream)
            writer.writerow(["date", "open", "high", "low", "close", "volume"])
            writer.writerows([[d, 100, 100, 100, 100, 1] for d in dates])
    spec = dict(
        schema="competition.dataset_spec.v1"
        if crypto
        else "competition.dataset_spec.v2",
        dataset_id="synthetic-study-contract",
        version="v1",
        source="binance_spot" if crypto else "ibkr_daily",
        market="crypto" if crypto else "US",
        quote_currency="USDT" if crypto else "USD",
        products=products,
        start=dates[0],
        end=dates[-1],
        calendar="365" if crypto else "XNYS",
        timezone="UTC" if crypto else "America/New_York",
        price_basis="raw" if crypto else "split_adjusted",
        universe_status="fixed_current",
        budget=dict(requests=20, bytes=1000000, seconds=60),
    )
    receipt = dict(status="acquired", coverage={}, gaps=[])
    if crypto:
        write_json(root / "receipt.json", receipt)
        write_manifest(spec, root)
    else:
        spec["benchmark"] = "SPY"
        files = payload_files(root)
        receipt.update(
            spec_hash="a" * 64,
            retained_payload_bytes=sum(f["bytes"] for f in files),
            calendar=dict(sessions=dates, package_version="synthetic"),
        )
        write_json(root / "receipt.json", receipt)
        write_json(
            root / "manifest.json",
            dict(
                schema="competition.dataset_manifest.v2",
                spec=spec,
                spec_hash="a" * 64,
                status="acquired",
                coverage={},
                gaps=[],
                receipt=receipt,
                files=files,
                accepted_research=False,
            ),
        )
    return root / "manifest.json"


def check(config, output_root: Path) -> dict:
    output = validate_external(output_root)
    output.mkdir(parents=True, exist_ok=False)
    manifests = [
        str(synthetic_manifest(output / market, crypto=market == "crypto"))
        for market in ("US", "crypto")
    ]
    freeze_study(
        dict(schema="competition.evaluation_spec.v2", manifests=manifests, costs=COSTS),
        output / "plan",
        code_identity=source_identity(Path(__file__).resolve().parents[2]),
    )
    result = run_study(config, output / "plan/plan.json")
    completed = [r for r in result["jobs"] if r["status"] == "completed"]
    if len(completed) != 19 or any(
        r["market"] != "HK" and r["status"] != "completed" for r in result["jobs"]
    ):
        raise ValueError("SYNTHETIC_STUDY_DELIVERY_FAILED")
    for record in completed:
        metrics = record["metrics"]
        # Flat-price positive-momentum and strict trend signals stay in cash.
        active = record["strategy"] in {
            "buy_hold",
            "benchmark_buy_hold",
            "equal_weight",
        }
        expected = 1 / (1 + record["fee_bps"] / 10000) - 1 if active else 0
        if (
            not math.isclose(metrics["net_return"], expected, abs_tol=1e-12)
            or metrics["gross_return"] != 0
        ):
            raise ValueError("SYNTHETIC_STUDY_ACCOUNTING_MISMATCH")
        child = json.loads(Path(record["result_path"]).read_text(encoding="utf-8"))
        periods_path = Path(record["result_path"]).parent / "periods.json"
        if digest(periods_path) != child["artifacts"][0]["sha256"]:
            raise ValueError("SYNTHETIC_STUDY_ARTIFACT_CHANGED")
    report = dict(
        schema="competition.study_delivery.v1",
        synthetic=True,
        completed=len(completed),
        blocked=[
            dict(market=r["market"], reason=r["reason"])
            for r in result["jobs"]
            if r["status"] != "completed"
        ],
    )
    write_json(output / "delivery.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(load_config(args.config), args.output_root), indent=2))


if __name__ == "__main__":
    main()
