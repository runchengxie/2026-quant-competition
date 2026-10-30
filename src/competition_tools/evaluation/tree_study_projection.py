"""Read-only projection of independently verified retained results; never fits models."""

import argparse
import json
from pathlib import Path

from ..datasets.storage import digest
from ..project_storage import relocated_path
from .study_identity import canonical_hash
from .tree_study import read, rules
from .tree_study_publication import COUNTS, validate
from .tree_study_validation import verify


def project(protocol):
    verified = verify(protocol)
    binding = read(protocol)
    output, parent = (relocated_path(binding[k]) for k in ("output", "parent_equity"))
    report, old = read(output / "report.json"), read(parent / "report.json")
    provenance = {
        k: binding[k]
        for k in (
            "binding_sha256",
            "input_sha256",
            "parent_result_sha256",
            "parent_plan_sha256",
            "calendar_sha256",
            "leaf_code_sha256",
        )
    }
    provenance.update(
        root_lock_sha256=binding["locks"]["root"],
        equity_lock_sha256=binding["locks"]["equity"],
        report_sha256=digest(output / "report.json"),
        verification_sha256=canonical_hash(verified),
        source_identity_sha256=canonical_hash(binding["source"]),
    )
    models = []
    for row in report["models"]:
        models.append(
            {k: row[k] for k in ("horizon", "window", "end", "model", "status")}
            | {
                k: row["metrics"][k]
                for k in (
                    "requested_dates",
                    "valid_ic_dates",
                    "valid_mse_dates",
                    "mean_daily_ic",
                    "mean_daily_mse",
                )
            }
        )
    accounts = {
        (r["horizon"], r["window"], r["arm"], r["buffer"], r["fee_bps"], r["delay"]): r
        for r in old["accounts"] + report["accounts"]
    }
    comparisons = []
    for row in verified["paired"]["returns"]:
        ref_buffer = 0 if row["reference"] == "equal_weight" else row["buffer"]
        left, right = (
            accounts[
                row["horizon"], row["window"], arm, buffer, row["fee_bps"], row["delay"]
            ]
            for arm, buffer in (
                (row["arm"], row["buffer"]),
                (row["reference"], ref_buffer),
            )
        )
        # Explicit derived-field allowlist. Do not copy arbitrary private report fields.
        public = {
            k: row[k]
            for k in (
                "horizon",
                "window",
                "arm",
                "reference",
                "buffer",
                "fee_bps",
                "delay",
                "difference",
                "reason",
                "arm_status",
                "reference_status",
            )
        }
        public.update(
            end=left["end"],
            reference_buffer=ref_buffer,
            arm_reason=left["reason"],
            reference_reason=right["reason"],
            arm_net_return=left["metrics"]["net_return"] if left["metrics"] else None,
            reference_net_return=right["metrics"]["net_return"]
            if right["metrics"]
            else None,
        )
        comparisons.append(public)
    return validate(
        dict(
            schema="competition.public_tree_study.v1",
            protocol=verified["protocol"],
            retrospective=True,
            formal_performance_ready=False,
            scientific_requirements="all_six_remain_blocked",
            uncertainty="unavailable_uncertainty_tooling_not_validated",
            rules=rules(),
            provenance=provenance,
            counts=dict(COUNTS),
            models=models,
            comparisons=comparisons,
        )
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument(
        "--output", required=True, help="New private candidate file; refuses overwrite"
    )
    args = parser.parse_args(argv)
    value = project(args.protocol)
    with Path(args.output).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
    print(canonical_hash(value))


if __name__ == "__main__":
    main()
