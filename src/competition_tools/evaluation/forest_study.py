"""Stdlib-only freeze, reserve and launch for the opt-in retrospective study."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from ..datasets.daily_storage import safe_path
from ..datasets.storage import digest
from ..project_storage import relocated_path
from .research_reservation import reserve_run, validate_reservation
from .study_identity import canonical_hash, source_identity

PROTOCOL = "equity.low_turnover_forest.20261031.v1"
SCHEMA = "competition.low_turnover_forest_protocol.v1"
RETAINED_INPUT = "08244582811c67fa2d4263c9b2a7515446f1b69efa4b00ad2b00c8aa155936e6"


def rules():
    return dict(
        horizons=[5, 20],
        windows=[["2026-05-28", "2026-07-24"], ["2026-07-27", "2026-09-21"]],
        validation_sessions=60,
        inner_calendar_minimum=80,
        models=["random_forest", "extra_trees"],
        depths=[3, 5],
        estimator_parameters={
            kind: [forest_parameters(kind, depth) for depth in (3, 5)]
            for kind in ("random_forest", "extra_trees")
        },
        sklearn="1.7.2",
        preprocessing="training_only_median_keep_empty_features",
        features=[
            "session_return",
            "range_fraction",
            "relative_dollar_volume",
            "median_spread",
            "quote_fraction",
            "active_fraction",
        ],
        minimum_candidates=30,
        minimum_validation_dates=20,
        selection="mean_daily_rank_ic_then_mse_then_declared_order",
        maximum_attempts_per_horizon=12,
        maximum_attempts_total=24,
        paired_return_hypotheses=576,
        seconds_per_horizon=1200,
        threads=2,
        new_requested_accounts=96,
        reused_requested_accounts=264,
        top_n=50,
        buffers=[0, 20],
        fees=[0, 20, 40],
        delays=[0, 1],
        accounting="raw_open_holding_cash.v1",
        currency="USD",
        paired_summaries="cellwise_net_return_and_equal_cohort_daily_rank_ic",
        uncertainty="unavailable_uncertainty_tooling_not_validated",
        retrospective=True,
        formal_performance_ready=False,
        scientific_requirements="all_six_remain_blocked",
    )


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_FOREST_FIELD")
            result[key] = value
        return result

    return json.loads(
        relocated_path(path).read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError("NONFINITE_FOREST_JSON")
        ),
    )


def write_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def leaf_code(source):
    root = source / "research/equity-lab/src/equity_lab"
    hasher = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        if path.is_symlink() or path.is_junction():
            raise ValueError("FOREST_SOURCE_REPARSE_PATH")
        hasher.update(path.relative_to(root).as_posix().encode())
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def forest_parameters(kind, depth):
    """Independent stdlib copy of the pinned complete sklearn constructor."""
    return dict(
        n_estimators=100,
        criterion="squared_error",
        max_depth=depth,
        min_samples_split=2,
        min_samples_leaf=100,
        min_weight_fraction_leaf=0.0,
        max_features=1.0,
        max_leaf_nodes=None,
        min_impurity_decrease=0.0,
        bootstrap=kind == "random_forest",
        oob_score=False,
        n_jobs=2,
        random_state=42,
        verbose=0,
        warm_start=False,
        ccp_alpha=0.0,
        max_samples=None,
        monotonic_cst=None,
    )


def _retained_records(root):
    """Inspect original entries before file tests or traversal can follow links."""
    root = relocated_path(root)
    pending, records = [root], []
    while pending:
        directory = pending.pop()
        for original in sorted(directory.iterdir()):
            path = relocated_path(original)
            if path.is_dir():
                pending.append(path)
            elif path.is_file():
                records.append(
                    dict(
                        path=path.relative_to(root).as_posix(),
                        bytes=path.stat().st_size,
                        sha256=digest(path),
                    )
                )
            else:
                raise ValueError("FOREST_UNKNOWN_RETAINED_ENTRY")
    return sorted(records, key=lambda row: row["path"])


def _source_root(value):
    # Source trees intentionally contain .git. The data-path guard cannot be
    # used here, but original source aliases must be rejected before resolve.
    original = Path(value).expanduser()
    if ".." in original.parts:
        raise ValueError("FOREST_INVALID_SOURCE_PATH")
    if not original.is_absolute():
        original = Path.cwd() / original
    if any(
        path.is_symlink() or path.is_junction()
        for path in (original, *original.parents)
    ):
        raise ValueError("FOREST_SOURCE_REPARSE_PATH")
    return original.resolve(strict=True)


def freeze_parent(tree_protocol, input_path):
    from .tree_study import verify_binding as tree_binding
    from .tree_study_validation import verify as verify_tree
    from .tree_study_publication import REVIEWED_SHA256, validate as validate_public

    frozen = tree_binding(tree_protocol, current_source=False)
    checked = verify_tree(tree_protocol)
    prepared = relocated_path(input_path)
    if digest(prepared) != frozen["input_sha256"]:
        raise ValueError("FOREST_REUSED_INPUT_CHANGED")
    public = json.loads(
        (
            Path(__file__).resolve().parents[3] / "site/src/data/tree-study.v1.json"
        ).read_text(encoding="utf-8")
    )
    validate_public(public)
    if canonical_hash(public) != REVIEWED_SHA256:
        raise ValueError("FOREST_REVIEWED_TREE_PUBLIC_CHANGED")
    if frozen["input_sha256"] == RETAINED_INPUT:
        from .tree_study_projection import project

        if canonical_hash(project(tree_protocol)) != REVIEWED_SHA256:
            raise ValueError("FOREST_RETAINED_TREE_PUBLIC_BINDING_CHANGED")
    output = relocated_path(frozen["output"])
    records = _retained_records(output)
    if checked["reused_requested_accounts"] + checked["new_requested_accounts"] != 264:
        raise ValueError("FOREST_REUSED_ACCOUNT_FAMILY_CHANGED")
    fields = (
        "parent_run",
        "parent_equity",
        "input_sha256",
        "parent_result_sha256",
        "parent_plan_sha256",
        "parent_records",
        "calendar_sha256",
    )
    return {k: frozen[k] for k in fields} | dict(
        input=str(prepared),
        tree_protocol=str(relocated_path(tree_protocol)),
        tree_binding_sha256=frozen["binding_sha256"],
        tree_output=str(output),
        tree_records=records,
        tree_verified_sha256=canonical_hash(checked),
        tree_public_sha256=REVIEWED_SHA256,
    )


def prepare(owner, tree_protocol, input_path, output, source_root):
    owner, output = relocated_path(owner), relocated_path(output)
    if not output.is_relative_to(owner) or output == owner:
        raise ValueError("FOREST_OUTPUT_OWNER_MISMATCH")
    source = _source_root(source_root)
    binding = dict(
        schema=SCHEMA,
        protocol=PROTOCOL,
        rules=rules(),
        **freeze_parent(tree_protocol, input_path),
        source=source_identity(source),
        leaf_code_sha256=leaf_code(source),
        locks={
            "root": digest(source / "uv.lock"),
            "equity": digest(source / "research/equity-lab/uv.lock"),
        },
        owner=str(owner),
        output=str(output),
    )
    binding["binding_sha256"] = canonical_hash(binding)
    # The protocol is beside, never inside, the new result directory.
    folder = owner / "research/forest-study-protocols"
    folder.mkdir(parents=True, exist_ok=True)
    path = safe_path(folder / (binding["binding_sha256"] + ".json"))
    identity = dict(
        protocol=PROTOCOL,
        input_sha256=binding["input_sha256"],
        code_sha256=binding["leaf_code_sha256"],
        lock_sha256=binding["locks"]["equity"],
        binding_sha256=binding["binding_sha256"],
        binding=str(path),
    )
    reservation = reserve_run(owner, identity, output)
    # Reservation first: a failed protocol write must not mint a second budget.
    write_new(path, binding)
    return dict(protocol=str(path), reservation=str(reservation), output=str(output))


def verify_binding(path, *, current_source=True):
    binding = read(relocated_path(path))
    fields = {
        "schema",
        "protocol",
        "rules",
        "parent_run",
        "parent_equity",
        "input",
        "input_sha256",
        "parent_result_sha256",
        "parent_plan_sha256",
        "parent_records",
        "tree_protocol",
        "tree_binding_sha256",
        "tree_output",
        "tree_records",
        "tree_verified_sha256",
        "tree_public_sha256",
        "calendar_sha256",
        "source",
        "leaf_code_sha256",
        "locks",
        "owner",
        "output",
        "binding_sha256",
    }
    if (
        set(binding) != fields
        or binding["schema"] != SCHEMA
        or binding["protocol"] != PROTOCOL
        or canonical_hash(binding["rules"]) != canonical_hash(rules())
        or canonical_hash({k: v for k, v in binding.items() if k != "binding_sha256"})
        != binding["binding_sha256"]
    ):
        raise ValueError("INVALID_FOREST_PROTOCOL")
    parent = freeze_parent(binding["tree_protocol"], binding["input"])
    for key, value in parent.items():
        if key in (
            "parent_run",
            "parent_equity",
            "input",
            "tree_protocol",
            "tree_output",
        ):
            if relocated_path(binding[key]) != relocated_path(value):
                raise ValueError("FOREST_PARENT_LOCATION_CHANGED")
        elif binding[key] != value:
            raise ValueError("FOREST_PARENT_BINDING_CHANGED")
    if current_source:
        source = Path(binding["source"]["source_root"])
        if (
            source_identity(source) != binding["source"]
            or leaf_code(source) != binding["leaf_code_sha256"]
            or {
                "root": digest(source / "uv.lock"),
                "equity": digest(source / "research/equity-lab/uv.lock"),
            }
            != binding["locks"]
        ):
            raise ValueError("FOREST_SOURCE_OR_LOCK_CHANGED")
    return binding


def launch_command(binding, reservation, python):
    return [
        str(python),
        "-m",
        "equity_lab.predictive.forest_study_cli",
        "--input",
        str(relocated_path(binding["input"])),
        "--output",
        str(relocated_path(binding["output"])),
        "--reservation",
        str(relocated_path(reservation)),
    ]


def run(protocol, reservation, python):
    binding = verify_binding(protocol)
    if binding["input_sha256"] != RETAINED_INPUT:
        raise ValueError("FOREST_RETAINED_INPUT_REQUIRED")
    identity = read(relocated_path(reservation))["identity"]
    if (
        identity.get("binding_sha256") != binding["binding_sha256"]
        or relocated_path(identity.get("binding", "")) != relocated_path(protocol)
        or identity.get("code_sha256") != binding["leaf_code_sha256"]
        or identity.get("lock_sha256") != binding["locks"]["equity"]
        or identity.get("input_sha256") != binding["input_sha256"]
        or identity.get("protocol") != PROTOCOL
    ):
        raise ValueError("FOREST_RESERVATION_BINDING_CHANGED")
    validate_reservation(reservation, identity, binding["output"])
    command = launch_command(binding, reservation, python)
    env = {
        **os.environ,
        "OMP_NUM_THREADS": "2",
        "OPENBLAS_NUM_THREADS": "2",
        "MKL_NUM_THREADS": "2",
        "PYTHONDONTWRITEBYTECODE": "1",
        "MPLBACKEND": "Agg",
    }
    result = subprocess.run(command, env=env, timeout=2500, check=False)
    if result.returncode:
        raise RuntimeError(f"FOREST_LEAF_FAILED_{result.returncode}")
    verify_binding(protocol)
    from .forest_study_validation import verify

    result = verify(protocol)
    write_new(relocated_path(binding["output"]) / "verification.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Explicit reserved retrospective tree study; no execution handoff"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    for name in (
        "owner",
        "tree-protocol",
        "input",
        "output",
        "source-root",
    ):
        prepare_parser.add_argument("--" + name, type=Path, required=True)
    for name in ("run", "verify"):
        child = commands.add_parser(name)
        child.add_argument("--protocol", type=Path, required=True)
        if name == "run":
            child.add_argument("--reservation", type=Path, required=True)
            child.add_argument("--python", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare(
            args.owner,
            args.tree_protocol,
            args.input,
            args.output,
            args.source_root,
        )
    elif args.command == "run":
        result = run(args.protocol, args.reservation, args.python)
    else:
        from .forest_study_validation import verify

        result = verify(args.protocol)
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
