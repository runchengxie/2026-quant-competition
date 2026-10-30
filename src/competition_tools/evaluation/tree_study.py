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
from .low_turnover_evidence import verify_holding_export
from .research_reservation import reserve_run, validate_reservation
from .run_record import verify_run
from .study_identity import canonical_hash, source_identity

PROTOCOL = "equity.low_turnover_tree.20261031.v1"
SCHEMA = "competition.low_turnover_tree_protocol.v1"


def rules():
    return dict(
        horizons=[5, 20],
        windows=[["2026-05-28", "2026-07-24"], ["2026-07-27", "2026-09-21"]],
        validation_sessions=60,
        inner_calendar_minimum=80,
        depths=[2, 3],
        max_iter=100,
        learning_rate=0.05,
        max_leaf_nodes=7,
        min_samples_leaf=100,
        l2_regularization=1.0,
        max_bins=63,
        seed=42,
        early_stopping=False,
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
        maximum_attempts_per_horizon=6,
        seconds_per_horizon=1200,
        threads=2,
        new_requested_accounts=96,
        reused_requested_accounts=168,
        top_n=50,
        buffers=[0, 20],
        fees=[0, 20, 40],
        delays=[0, 1],
        momentum="close_t_over_close_t_minus_20_contiguous_no_action_or_ticker_change",
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
                raise ValueError("DUPLICATE_TREE_FIELD")
            result[key] = value
        return result

    return json.loads(
        relocated_path(path).read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError("NONFINITE_TREE_JSON")
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
            raise ValueError("TREE_SOURCE_REPARSE_PATH")
        hasher.update(path.relative_to(root).as_posix().encode())
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def freeze_parent(parent_run, parent_equity, input_path):
    run, equity, prepared = map(relocated_path, (parent_run, parent_equity, input_path))
    checked = verify_run(run)
    if not equity.is_relative_to(run) or equity == run:
        raise ValueError("PARENT_EQUITY_OUTSIDE_RUN")
    report = read(equity / "report.json")
    plan = read(run / "experiment-plan.json")
    hashed = digest(prepared)
    if (
        report.get("schema") != "equity.low_turnover_ml.v2"
        or report.get("validation_sessions") != 60
        or report.get("protocol") != "equity.holding_validation60.20261025.v1"
        or report.get("input_sha256") != hashed
        or report.get("source_unchanged") is not True
        or not any(r["sha256"] == hashed for r in plan["inputs"])
    ):
        raise ValueError("PARENT_INPUT_OR_PROFILE_BINDING_MISSING")
    windows = sorted({(r["window"], r["end"]) for r in report["models"]})
    if [list(w) for w in windows] != rules()["windows"]:
        raise ValueError("PARENT_EXPOSED_WINDOWS_CHANGED")
    prefix = equity.relative_to(run).as_posix() + "/"
    records = [r for r in checked["artifacts"] if r["path"].startswith(prefix)]
    declared = {r["path"] for r in records}
    actual = {p.relative_to(run).as_posix() for p in equity.rglob("*") if p.is_file()}
    if actual != declared or not records:
        raise ValueError("UNBOUND_PARENT_HOLDING_FILE")
    verified = verify_holding_export(equity)
    if len(verified["accounts"]) != 168:
        raise ValueError("PARENT_ACCOUNT_BINDING_MISSING")
    return dict(
        parent_run=str(run),
        parent_equity=str(equity),
        input=str(prepared),
        input_sha256=hashed,
        parent_result_sha256=checked["result_sha256"],
        parent_plan_sha256=plan["plan_sha256"],
        parent_records=records,
        calendar_sha256=canonical_hash(report["calendar"]),
    )


def prepare(owner, parent_run, parent_equity, input_path, output, source_root):
    owner, output = relocated_path(owner), relocated_path(output)
    if not output.is_relative_to(owner) or output == owner:
        raise ValueError("TREE_OUTPUT_OWNER_MISMATCH")
    source = Path(source_root).resolve(strict=True)
    binding = dict(
        schema=SCHEMA,
        protocol=PROTOCOL,
        rules=rules(),
        **freeze_parent(parent_run, parent_equity, input_path),
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
    folder = owner / "research/tree-study-protocols"
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
        raise ValueError("INVALID_TREE_PROTOCOL")
    parent = freeze_parent(
        binding["parent_run"], binding["parent_equity"], binding["input"]
    )
    for key, value in parent.items():
        if key in ("parent_run", "parent_equity", "input"):
            if relocated_path(binding[key]) != relocated_path(value):
                raise ValueError("TREE_PARENT_LOCATION_CHANGED")
        elif binding[key] != value:
            raise ValueError("TREE_PARENT_BINDING_CHANGED")
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
            raise ValueError("TREE_SOURCE_OR_LOCK_CHANGED")
    return binding


def launch_command(binding, reservation, python):
    return [
        str(python),
        "-m",
        "equity_lab.predictive.tree_study_cli",
        "--input",
        str(relocated_path(binding["input"])),
        "--output",
        str(relocated_path(binding["output"])),
        "--reservation",
        str(relocated_path(reservation)),
    ]


def run(protocol, reservation, python):
    binding = verify_binding(protocol)
    identity = read(relocated_path(reservation))["identity"]
    if (
        identity.get("binding_sha256") != binding["binding_sha256"]
        or relocated_path(identity.get("binding", "")) != relocated_path(protocol)
        or identity.get("code_sha256") != binding["leaf_code_sha256"]
        or identity.get("lock_sha256") != binding["locks"]["equity"]
        or identity.get("input_sha256") != binding["input_sha256"]
        or identity.get("protocol") != PROTOCOL
    ):
        raise ValueError("TREE_RESERVATION_BINDING_CHANGED")
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
        raise RuntimeError(f"TREE_LEAF_FAILED_{result.returncode}")
    verify_binding(protocol)
    from .tree_study_validation import verify

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
        "parent-run",
        "parent-equity",
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
            args.parent_run,
            args.parent_equity,
            args.input,
            args.output,
            args.source_root,
        )
    elif args.command == "run":
        result = run(args.protocol, args.reservation, args.python)
    else:
        from .tree_study_validation import verify

        result = verify(args.protocol)
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
