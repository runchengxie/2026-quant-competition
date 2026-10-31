"""Freeze and independently verify NEW private diagnostics of exposed saved history."""

import argparse
import json
import os
import subprocess
from pathlib import Path

from ..datasets.storage import digest
from ..project_storage import CANONICAL, relocated_path
from .comparison_evidence import _csv
from .low_turnover_evidence import load_observations
from .posthoc_reference import evaluate, same
from .study_identity import canonical_hash, source_identity
from .tree_study import read, verify_binding as tree_binding, write_new
from .tree_study_validation import scores, target, verify as verify_tree
from .tree_study_publication import parse_reviewed, REVIEWED_SHA256

SCHEMA = "competition.posthoc_diagnostics_protocol.v1"


def rules():
    return dict(
        history="POSTHOC_EXPOSED_HISTORY",
        horizons=[1, 5, 10, 20],
        family_size=64,
        statistic="one_daily_cross_sectional_rank_ic_equal_session_weight",
        label_interval="t_plus_1_open_to_t_plus_h_close_future_only_validity_actions_identity",
        quintiles="linear_all_finite_decision_scores_before_label_mask_first_upper_edge_ge",
        minimum_distinct_scores=5,
        strict_increasing_edges=True,
        minimum_candidates=30,
        hac="bartlett_lag_h_minus_1_n_over_n_minus_1",
        ci="normal_95_diagnostic",
        p="two_sided_erfc_abs_mean_over_se_sqrt2",
        bootstrap="noncircular_moving_blocks_ceil_n_over_length_then_truncate",
        block_length="max_5_h",
        draws=2000,
        seed=20261031,
        rng="python_random_Random_randrange_reset_per_hypothesis",
        eligibility="complete_contiguous_n_ge_30_and_4h_and_4block_nonconstant",
        multiplicity="holm_complete_64_unavailable_padded_1_output_unavailable",
        adaptive_search_correction=False,
        formal_performance_ready=False,
        quintile_long_short_in_family=False,
        fit_authorization=0,
    )


def canonical_location(path):
    path = relocated_path(path)
    if not any(p.name == CANONICAL for p in (path, *path.parents)):
        raise ValueError("POSTHOC_CANONICAL_DATA_ROOT_REQUIRED")
    return path


def snapshot(folder):
    records = []
    for path in sorted(folder.rglob("*")):
        relocated_path(path)
        if path.is_file():
            records.append(
                dict(
                    path=path.relative_to(folder).as_posix(),
                    bytes=path.stat().st_size,
                    sha256=digest(path),
                )
            )
    return records


def saved_inputs(protocol):
    """Read verified CSV exports only; no parquet decode, acquisition or fits."""
    verified = verify_tree(protocol)
    binding = tree_binding(protocol, current_source=False)
    parent, tree = map(relocated_path, (binding["parent_equity"], binding["output"]))
    old, new = read(parent / "report.json"), read(tree / "report.json")
    calendar = old["calendar"]
    days = calendar[:-21][-80:]
    windows = {days[0]: days[:40], days[40]: days[40:]}
    cohorts = {d: [] for d in days}
    for row in _csv(
        parent / "decisions.csv",
        ["date", "candidate_id", "session_return", "price_valid"],
    ):
        if row["date"] in cohorts:
            cohorts[row["date"]].append(row["candidate_id"])
    for names in cohorts.values():
        names.sort()
    observations = load_observations(parent)
    blocks = []
    for folder, report in ((parent, old), (tree, new)):
        for row in report["models"]:
            h, w, model = row["horizon"], row["window"], row["model"]
            if row["status"] != "completed":
                raise ValueError("POSTHOC_REQUIRES_COMPLETE_SAVED_BLOCKS")
            prefix = folder if folder == parent else folder / f"h{h}"
            values = scores(
                prefix / f"h{h}-{w}-{model}-predictions.csv",
                {(d, n) for d in windows[w] for n in cohorts[d]},
                missing=True,
            )
            blocks.append(
                dict(
                    id=f"h{h}-{w}-{model}",
                    model=model,
                    training_horizon=h,
                    window=w,
                    sessions=windows[w],
                    scores=[
                        [d, n, values[d, n]] for d in windows[w] for n in cohorts[d]
                    ],
                )
            )
    blocks.sort(key=lambda b: b["id"])
    expected = {
        (h, w, m)
        for h in (5, 20)
        for w in windows
        for m in ("ridge", "elastic_net", "shallow_tree", "momentum20")
    }
    if {
        (b["training_horizon"], b["window"], b["model"]) for b in blocks
    } != expected or len(blocks) != 16:
        raise ValueError("POSTHOC_SAVED_MODEL_FAMILY_CHANGED")
    evidence = dict(
        schema="equity.posthoc_inputs.v1",
        calendar=calendar,
        cohorts=cohorts,
        observations=[
            [d, n, r["ticker"], r["open"], r["close"], r["valid"], r["action_boundary"]]
            for (d, n), r in sorted(observations.items())
        ],
        blocks=blocks,
        original_labels=[
            [d, n, h, target(observations, calendar, h, d, n)]
            for d in days
            for n in cohorts[d]
            for h in (5, 20)
        ],
    )
    parents = dict(
        tree_protocol=str(relocated_path(protocol)),
        tree_binding_sha256=binding["binding_sha256"],
        tree_verification_sha256=canonical_hash(verified),
        input_sha256=binding["input_sha256"],
        parent_result_sha256=binding["parent_result_sha256"],
        parent_records=snapshot(parent),
        tree_records=snapshot(tree),
    )
    return evidence, parents


def no_reparse(path):
    path = Path(path).absolute()
    if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
        raise ValueError("POSTHOC_SOURCE_REPARSE_PATH")
    return path


def source_record(source):
    source = no_reparse(source).resolve(strict=True)
    for tree in ("src", "research/equity-lab/src", "research/crypto-mm/src"):
        root = no_reparse(source / tree)
        for path in root.rglob("*"):
            no_reparse(path)
    status = subprocess.run(
        ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if status.stdout.strip():
        raise ValueError("POSTHOC_COMMITTED_CLEAN_SOURCE_REQUIRED")
    public = no_reparse(source / "site/src/data/tree-study.v1.json")
    parse_reviewed(public.read_text(encoding="utf-8"))
    return dict(
        identity=source_identity(source),
        original_public=dict(
            semantic_sha256=REVIEWED_SHA256, bytes_sha256=digest(public)
        ),
        locks={
            name: digest(no_reparse(source / name))
            for name in ("uv.lock", "research/equity-lab/uv.lock")
        },
    )


def prepare(parent_protocol, owner, output, source):
    owner, output = canonical_location(owner), canonical_location(output)
    if (
        owner.exists()
        or output.exists()
        or owner == output
        or owner.is_relative_to(output)
    ):
        raise ValueError("POSTHOC_EXCLUSIVE_NEW_LOCATIONS_REQUIRED")
    source = source_record(source)
    evidence, parents = saved_inputs(parent_protocol)
    family = [
        dict(block=b["id"], horizon=h)
        for b in evidence["blocks"]
        for h in (1, 5, 10, 20)
    ]
    binding = dict(
        schema=SCHEMA,
        rules=rules(),
        source=source,
        parents=parents,
        owner=str(owner),
        output=str(output),
        evidence_sha256=canonical_hash(evidence),
        family=family,
    )
    binding["binding_sha256"] = canonical_hash(binding)
    owner.mkdir(parents=True, exist_ok=False)
    write_new(owner / "inputs.json", evidence)
    write_new(owner / "protocol.json", binding)
    return dict(
        protocol=str(owner / "protocol.json"),
        output=str(output),
        binding_sha256=binding["binding_sha256"],
    )


def check_protocol(protocol, *, current_source=True):
    path = canonical_location(protocol)
    b = read(path)
    if (
        set(b)
        != {
            "schema",
            "rules",
            "source",
            "parents",
            "owner",
            "output",
            "evidence_sha256",
            "family",
            "binding_sha256",
        }
        or b["schema"] != SCHEMA
        or b["rules"] != rules()
    ):
        raise ValueError("INVALID_POSTHOC_PROTOCOL")
    if (
        canonical_hash({k: v for k, v in b.items() if k != "binding_sha256"})
        != b["binding_sha256"]
    ):
        raise ValueError("POSTHOC_PROTOCOL_HASH_CHANGED")
    owner, output = canonical_location(b["owner"]), canonical_location(b["output"])
    if (
        path != owner / "protocol.json"
        or output == owner
        or owner.is_relative_to(output)
    ):
        raise ValueError("POSTHOC_LOCATION_CHANGED")
    if current_source:
        same(source_record(b["source"]["identity"]["source_root"]), b["source"])
    evidence, parents = saved_inputs(b["parents"]["tree_protocol"])
    same(parents, b["parents"])
    if (
        canonical_hash(evidence) != b["evidence_sha256"]
        or canonical_hash(read(owner / "inputs.json")) != b["evidence_sha256"]
    ):
        raise ValueError("POSTHOC_INPUT_HASH_CHANGED")
    if b["family"] != [
        dict(block=block["id"], horizon=h)
        for block in evidence["blocks"]
        for h in (1, 5, 10, 20)
    ]:
        raise ValueError("POSTHOC_FAMILY_CHANGED")
    return b, evidence


def verify(protocol):
    b, evidence = check_protocol(protocol, current_source=False)
    output = canonical_location(b["output"])
    required = {"started.json", "producer-started.json", "report.json"}
    names = {p.name for p in output.iterdir()}
    if names not in (required, required | {"verification.json"}):
        raise ValueError("POSTHOC_OUTPUT_FILES_CHANGED")
    for name in ("started.json", "producer-started.json"):
        same(read(output / name), dict(binding_sha256=b["binding_sha256"]))
    report = read(output / "report.json")
    same(
        report,
        dict(binding_sha256=b["binding_sha256"], **evaluate(evidence, b["family"])),
    )
    result = dict(
        schema="competition.posthoc_diagnostics_verified.v1",
        binding_sha256=b["binding_sha256"],
        report_sha256=canonical_hash(report),
        history="POSTHOC_EXPOSED_HISTORY",
        family_size=64,
        formal_performance_ready=False,
        scientific_requirements="all_six_remain_blocked",
    )
    if (output / "verification.json").exists():
        same(read(output / "verification.json"), result)
    return result


def run(protocol, python):
    b, _ = check_protocol(protocol)
    output = canonical_location(b["output"])
    output.mkdir(parents=True, exist_ok=False)
    # Durable claim precedes the child; failed/partial output is retained, never retried here.
    write_new(output / "started.json", dict(binding_sha256=b["binding_sha256"]))
    command = [
        str(python),
        "-m",
        "equity_lab.evaluation.posthoc_cli",
        "--protocol",
        str(protocol),
    ]
    result = subprocess.run(
        command,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
        timeout=1800,
    )
    if result.returncode:
        raise RuntimeError(f"POSTHOC_LEAF_FAILED_{result.returncode}")
    check_protocol(protocol)
    verified = verify(protocol)
    write_new(output / "verification.json", verified)
    return verified


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    prepare_parser = sub.add_parser("prepare")
    for name in ("parent-protocol", "owner", "output", "source"):
        prepare_parser.add_argument("--" + name, required=True)
    for action in ("run", "verify"):
        child = sub.add_parser(action)
        child.add_argument("--protocol", required=True)
        if action == "run":
            child.add_argument("--python", required=True)
    args = vars(parser.parse_args(argv))
    action = args.pop("action")
    print(json.dumps(globals()[action](**args), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
