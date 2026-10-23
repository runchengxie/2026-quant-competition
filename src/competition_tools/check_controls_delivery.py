"""No-network installed controls delivery using explicitly synthetic prices."""

import argparse
import json
import math
from pathlib import Path

from .check_study_delivery import synthetic_manifest
from .datasets.daily_storage import safe_path
from .datasets.storage import digest, write_json
from .evaluation.controls.catalog import ARMS, BUDGET, COSTS
from .evaluation.controls.plan import freeze_controls
from .evaluation.controls.publication import build_public_controls
from .evaluation.controls.runner import run_controls
from .evaluation.study_identity import source_identity
from .team.config import load_config


def reference_return(market, arm, fee_bps):
    """Solve initial cash = post-fee NAV + commission, independently of leaves."""
    gross_weight = 0.0
    if market == "US" and arm.startswith("ew_"):
        gross_weight = 1.0
    elif market == "crypto":
        gross_weight = {"ew_legacy": 1.0, "ew_fixed60": 0.6}.get(arm, 0.0)
    return 1 / (1 + gross_weight * fee_bps / 10000) - 1


def check_controls_delivery(config, output_root: Path) -> dict:
    output = safe_path(output_root)
    output.mkdir(parents=True, exist_ok=False)
    manifests = {
        market: str(synthetic_manifest(output / market, crypto=market == "crypto"))
        for market in ("US", "crypto")
    }
    spec = dict(
        schema="competition.strategy_controls_spec.v1",
        manifests=manifests,
        expected_input_hashes={m: digest(Path(p)) for m, p in manifests.items()},
        arms=ARMS,
        costs=COSTS,
        role="retrospective",
        accepted_research=False,
        budget=BUDGET,
    )
    freeze_controls(
        spec,
        output / "study",
        code_identity=source_identity(Path(__file__).resolve().parents[2]),
    )
    result = run_controls(config, output / "study/plan.json")
    if result["status"] != "completed" or len(result["jobs"]) != 36:
        raise ValueError("SYNTHETIC_CONTROLS_DELIVERY_FAILED")
    for row in result["jobs"]:
        expected = reference_return(row["market"], row["arm_id"], row["fee_bps"])
        if (
            not math.isclose(row["metrics"]["net_return"], expected, abs_tol=1e-12)
            or row["metrics"]["gross_return"] != 0
        ):
            raise ValueError("SYNTHETIC_CONTROLS_ACCOUNTING_MISMATCH")
    public = build_public_controls(
        output / "study/plan.json",
        output / "study/run/results.json",
        publication_review={},
    )
    if public["status"] != "readiness_only" or public["results"] or public["pairs"]:
        raise ValueError("SYNTHETIC_CONTROLS_PUBLICATION_MISMATCH")
    report = dict(
        schema="competition.strategy_controls_delivery.v1",
        synthetic=True,
        completed=len(result["jobs"]),
        blocked=0,
        independent_reference="constant_prices_post_fee_initial_cash_algebra",
        public_status=public["status"],
    )
    write_json(output / "delivery.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            check_controls_delivery(load_config(args.config), args.output_root),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
