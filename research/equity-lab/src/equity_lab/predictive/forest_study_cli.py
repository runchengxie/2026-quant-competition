"""Versioned file boundary with once-only reservation and hard horizon deadlines."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import signal

from equity_lab._project_storage import relocated_path
from equity_lab.run_guard import digest, claim_reservation, source_digest, lock_digest
from .forest_study import PROTOCOL, REPORT, run_forest_study, write
from .forest_study_guard import start_forest, claim_horizon
from .forest_profile import require_real_input


def bounded(command, seconds):
    """Terminate the whole owned worker tree, including Windows venv launchers."""
    with subprocess.Popen(
        command,
        env={
            **os.environ,
            "OMP_NUM_THREADS": "2",
            "OPENBLAS_NUM_THREADS": "2",
            "MKL_NUM_THREADS": "2",
        },
        start_new_session=os.name != "nt",
    ) as process:
        try:
            return process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                    timeout=15,
                )
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=15)
            raise


def missing_cells(binding, report, horizon, reason):
    present = {
        (r["window"], r["arm"], r["buffer"], r["fee_bps"], r["delay"])
        for r in report["accounts"]
        if r["horizon"] == horizon
    }
    return [
        dict(
            horizon=horizon,
            window=window,
            arm=arm,
            buffer=buffer,
            fee_bps=fee,
            delay=delay,
            reason=reason or "incomplete_worker_artifacts",
        )
        for window, _ in binding["rules"]["windows"]
        for arm in ("random_forest", "extra_trees")
        for buffer in (0, 20)
        for fee in (0, 20, 40)
        for delay in (0, 1)
        if (window, arm, buffer, fee, delay) not in present
    ]


def authoritative_attempt_count(reservation, horizon):
    path = relocated_path(
        str(relocated_path(reservation)) + f".h{horizon}.attempts.jsonl"
    )
    return len(path.read_text(encoding="utf-8").splitlines()) if path.is_file() else 0


def binding_for(reservation):
    receipt = json.loads(relocated_path(reservation).read_text(encoding="utf-8"))
    identity = receipt["identity"]
    binding = json.loads(
        relocated_path(identity["binding"]).read_text(encoding="utf-8")
    )
    require_real_input(binding)
    hashed = hashlib.sha256(
        json.dumps(
            {k: v for k, v in binding.items() if k != "binding_sha256"},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    if (
        binding["schema"] != "competition.low_turnover_forest_protocol.v1"
        or binding["protocol"] != PROTOCOL
        or hashed != binding["binding_sha256"]
        or hashed != identity["binding_sha256"]
        or digest(relocated_path(binding["input"])) != binding["input_sha256"]
        or relocated_path(receipt["output"]) != relocated_path(binding["output"])
    ):
        raise ValueError("FOREST_PROTOCOL_OR_INPUT_CHANGED")
    parent = relocated_path(binding["parent_run"])
    result = json.loads(
        relocated_path(parent / "experiment-result.json").read_text(encoding="utf-8")
    )

    def canonical(value):
        return hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()

    plan = json.loads(
        relocated_path(parent / "experiment-plan.json").read_text(encoding="utf-8")
    )
    if (
        result["result_sha256"] != binding["parent_result_sha256"]
        or canonical({k: v for k, v in result.items() if k != "result_sha256"})
        != binding["parent_result_sha256"]
        or plan["plan_sha256"] != binding["parent_plan_sha256"]
        or canonical({k: v for k, v in plan.items() if k != "plan_sha256"})
        != binding["parent_plan_sha256"]
        or result["plan_sha256"] != plan["plan_sha256"]
        or digest(relocated_path(parent / plan["code"]["archive"]))
        != plan["code"]["archive_sha256"]
    ):
        raise ValueError("FOREST_PARENT_RESULT_CHANGED")
    for record in plan["inputs"]:
        path = relocated_path(parent / record["path"])
        if (
            not path.is_relative_to(parent)
            or path.stat().st_size != record["bytes"]
            or digest(path) != record["sha256"]
        ):
            raise ValueError("FOREST_PARENT_INPUT_CHANGED")
    for record in binding["parent_records"]:
        path = relocated_path(parent / record["path"])
        if (
            not path.is_relative_to(parent)
            or path.stat().st_size != record["bytes"]
            or digest(path) != record["sha256"]
        ):
            raise ValueError("FOREST_PARENT_EXPORT_CHANGED")
    tree = relocated_path(binding["tree_output"])
    for record in binding["tree_records"]:
        path = relocated_path(tree / record["path"])
        if (
            not path.is_relative_to(tree)
            or path.stat().st_size != record["bytes"]
            or digest(path) != record["sha256"]
        ):
            raise ValueError("FOREST_REUSED_TREE_CHANGED")
    binding["parent_equity"] = str(relocated_path(binding["parent_equity"]))
    return binding


def horizon_worker(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon", type=int, choices=(5, 20), required=True)
    for name in ("input", "output", "reservation"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    binding = binding_for(args.reservation)
    receipt = json.loads(relocated_path(args.reservation).read_text(encoding="utf-8"))
    if (
        receipt["identity"]["code_sha256"] != source_digest()
        or receipt["identity"]["lock_sha256"] != lock_digest()
    ):
        raise ValueError("FOREST_CURRENT_SOURCE_CHANGED")
    root = relocated_path(binding["output"])
    output = relocated_path(args.output)
    if (
        output != root / f"h{args.horizon}"
        or relocated_path(args.input) != relocated_path(binding["input"])
        or not Path(str(relocated_path(args.reservation)) + ".started").is_file()
    ):
        raise ValueError("FOREST_HORIZON_NOT_RESERVED")
    claim = claim_horizon(args.reservation, binding, args.horizon)
    # A killed horizon cannot silently restart even if no fit was reached.
    with (root / f"h{args.horizon}.started").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(dict(pid=os.getpid(), horizon=args.horizon)))
        stream.flush()
        os.fsync(stream.fileno())
    import pandas as pd

    prepared = relocated_path(args.input)
    raw = pd.read_parquet(prepared)
    # Calendar is the frozen parent calendar, never inferred from future labels.
    schedule = pd.read_csv(
        Path(binding["parent_equity"]) / "calendar.csv", index_col="date"
    )
    schedule.index = pd.to_datetime(schedule.index)
    for name in ("open", "close"):
        schedule[name] = pd.to_datetime(schedule[name], utc=True)
    run_forest_study(
        raw, schedule, output, binding, horizons=(args.horizon,), claim=claim
    )
    if digest(prepared) != binding["input_sha256"]:
        raise ValueError("FOREST_INPUT_CHANGED_DURING_FIT")
    binding_for(args.reservation)
    if (
        receipt["identity"]["code_sha256"] != source_digest()
        or receipt["identity"]["lock_sha256"] != lock_digest()
    ):
        raise ValueError("FOREST_SOURCE_CHANGED_DURING_FIT")
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--horizon" in argv:
        return horizon_worker(argv)
    parser = argparse.ArgumentParser(
        description="Once-reserved bounded retrospective tree study"
    )
    for name in ("input", "output", "reservation"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    claim_reservation(
        args.reservation, args.input, args.output, PROTOCOL, claim=args.worker
    )
    if not args.worker:
        try:
            return bounded(
                [
                    sys.executable,
                    "-m",
                    "equity_lab.predictive.forest_study_cli",
                    *argv,
                    "--worker",
                ],
                2480,
            )
        except subprocess.TimeoutExpired:
            output = relocated_path(args.output)
            output.mkdir(parents=True, exist_ok=True)
            write(output / "timeout.json", dict(status="timeout", seconds=2480))
            return 2
    binding = binding_for(args.reservation)
    # Prove the claimed reservation still has this source identity. claim=False
    # cannot be reused here because it intentionally rejects the started marker.
    receipt = json.loads(relocated_path(args.reservation).read_text(encoding="utf-8"))
    if (
        receipt["identity"]["code_sha256"] != source_digest()
        or receipt["identity"]["lock_sha256"] != lock_digest()
    ):
        raise ValueError("FOREST_CURRENT_SOURCE_CHANGED")
    output = relocated_path(args.output)
    os.environ["GMR_FOREST_WORKER_TOKEN"] = start_forest(args.reservation, binding)
    output.mkdir(parents=True, exist_ok=False)
    report = dict(
        schema=REPORT,
        protocol=PROTOCOL,
        binding_sha256=binding["binding_sha256"],
        status="running",
        retrospective=True,
        formal_performance_ready=False,
        currency="USD",
        validation_sessions=60,
        reused_requested_accounts=264,
        new_requested_accounts=96,
        models=[],
        accounts=[],
        unavailable_cells=[],
        fit_attempts=0,
        horizons=[],
        uncertainty=dict(
            status="unavailable", reason="uncertainty_tooling_not_validated"
        ),
    )
    write(output / "report.json", report)
    for horizon in (5, 20):
        state = dict(horizon=horizon, status="running", reason=None)
        report["horizons"].append(state)
        write(output / "report.json", report)
        command = [
            sys.executable,
            "-m",
            "equity_lab.predictive.forest_study_cli",
            "--horizon",
            str(horizon),
            "--input",
            str(relocated_path(args.input)),
            "--output",
            str(output / f"h{horizon}"),
            "--reservation",
            str(relocated_path(args.reservation)),
        ]
        try:
            code = bounded(command, 1200)
            state.update(
                status="completed" if code == 0 else "failed",
                reason=None if code == 0 else f"worker_exit_{code}",
            )
        except subprocess.TimeoutExpired:
            state.update(status="timeout", reason="horizon_1200_second_deadline")
            write(output / f"h{horizon}-timeout.json", state)
        path = output / f"h{horizon}/report.json"
        if path.is_file():
            part = json.loads(path.read_text(encoding="utf-8"))
            for key in ("models", "accounts"):
                report[key].extend(part[key])
        # Count owner starts even when a kill interrupted the output mirror.
        report["fit_attempts"] += authoritative_attempt_count(args.reservation, horizon)
        report["unavailable_cells"].extend(
            missing_cells(binding, report, horizon, state["reason"])
        )
        write(output / "report.json", report)
    report["status"] = (
        "completed"
        if all(h["status"] == "completed" for h in report["horizons"])
        else "failed"
    )
    write(output / "report.json", report)
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
