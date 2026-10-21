"""No-network actual v2 producer/consumer check with synthetic provenance."""

import argparse
import json
import math
from pathlib import Path
from .check_study_delivery import synthetic_manifest
from .datasets.storage import digest, write_json
from .team.config import TeamConfig, load_config
from .team.paths import validate_external
from .evaluation.ablation_catalog import catalog
from .evaluation.ablation_plan import COSTS, freeze_ablation
from .evaluation.ablation_runner import run_ablation
from .evaluation.study_identity import source_identity


def synthetic_spec(root):
    root = validate_external(root)
    root.mkdir(parents=True, exist_ok=False)
    manifests = [
        str(synthetic_manifest(root / "stock", crypto=False)),
        str(synthetic_manifest(root / "crypto", crypto=True)),
    ]
    probe = root / "protocol.json"
    diagnostic = root / "diagnostic-protocol.json"
    evidence = root / "evidence.json"
    write_json(probe, dict(synthetic=True, retrospective=True, accepted_research=False))
    write_json(
        diagnostic,
        dict(
            synthetic=True,
            post_hoc=True,
            accepted_research=False,
            parent_protocol_sha256=digest(probe),
        ),
    )
    write_json(
        evidence,
        {
            "files": [
                dict(path=p.name, bytes=p.stat().st_size, sha256=digest(p))
                for p in [probe, diagnostic]
            ]
        },
    )
    return dict(
        schema="competition.evaluation_spec.v3",
        manifests=manifests,
        costs=COSTS,
        variants={
            m: [{k: p[k] for k in ["strategy", "variant_id"]} for p in items]
            for m, items in catalog().items()
            if m in {"US", "crypto"}
        },
        origin=dict(
            probe_protocol=str(probe),
            diagnostic_protocol=str(diagnostic),
            evidence_manifest=str(evidence),
        ),
    )


def check_ablation_delivery(config: TeamConfig, output_root: Path) -> dict:
    output = validate_external(output_root)
    output.mkdir(parents=True, exist_ok=False)
    spec = synthetic_spec(output / "inputs")
    freeze_ablation(
        spec,
        output / "study",
        code_identity=source_identity(Path(__file__).resolve().parents[2]),
    )
    result = run_ablation(config, output / "study/plan.json")
    completed = [r for r in result["jobs"] if r["status"] == "completed"]
    if len(completed) != 40 or any(
        r["market"] != "HK" and r["status"] != "completed" for r in result["jobs"]
    ):
        raise ValueError("SYNTHETIC_ABLATION_DELIVERY_FAILED")
    for r in completed:
        active = r["strategy"] in {"buy_hold", "benchmark_buy_hold", "equal_weight"}
        expected = 1 / (1 + r["fee_bps"] / 10000) - 1 if active else 0
        if (
            not math.isclose(
                r["metrics"]["net_return"], expected, rel_tol=0, abs_tol=1e-12
            )
            or r["metrics"]["gross_return"] != 0
        ):
            raise ValueError("SYNTHETIC_ABLATION_ACCOUNTING_MISMATCH")
    report = dict(
        schema="competition.ablation_delivery.v1",
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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    a = p.parse_args()
    print(
        json.dumps(
            check_ablation_delivery(load_config(a.config), a.output_root), indent=2
        )
    )


if __name__ == "__main__":
    main()
