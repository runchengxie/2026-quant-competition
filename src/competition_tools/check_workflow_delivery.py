"""Run two fictional offline pipelines and verify their immutable file contracts."""

import argparse
import csv
import hashlib
import json
import math
import platform
import re
import subprocess
import time
from datetime import date, timedelta
from pathlib import Path

from .check_workflow_boundaries import check_boundaries
from .datasets.daily_storage import safe_path
from .datasets.storage import digest
from .evaluation.contributions import explain_fractional, explain_self_financing
from .evaluation.run_record import init_run, freeze_run, finish_run, verify_run
from .evaluation.study_identity import source_hash
from .team.config import load_config
from .team.processes import child_environment, interpreter, run_child

PROJECTS = {
    "equity-lab": (
        "equity_lab.workflow",
        "equity_fractional_proxy.v1",
        (
            "prepared.csv",
            "signals.csv",
            "portfolio.csv",
            "positions.csv",
            "gross-portfolio.csv",
            "summary.json",
        ),
    ),
    "crypto-mm": (
        "crypto_mm.workflow",
        "self_financing_daily.v1",
        ("prices.json", "targets.json", "net.json", "gross.json", "summary.json"),
    ),
}
FIELDS = {
    "schema",
    "status",
    "project",
    "synthetic",
    "accounting_model",
    "quote_currency",
    "initial_equity",
    "parameters",
    "input_sha256",
    "code_sha256",
    "environment",
    "metrics",
    "evidence",
    "artifacts",
}


def _write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _read(path):
    path = safe_path(path)
    if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("INVALID_LEAF_FILE_SIZE")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=unique_object
    )
    json.dumps(value, allow_nan=False)
    return value


def package_digest(root: Path) -> str:
    root = Path(root).absolute()
    paths = sorted(root.rglob("*.py"))
    if not root.is_dir() or not paths:
        raise ValueError("LEAF_SOURCE_MISSING")
    hashed = hashlib.sha256()
    for path in paths:
        if any(
            p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
            for p in (path, *path.parents)
        ):
            raise ValueError("LEAF_SOURCE_REPARSE")
        hashed.update(path.relative_to(root).as_posix().encode())
        hashed.update(path.read_bytes())
    return hashed.hexdigest()


def synthetic_jobs() -> dict:
    dates = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(24)]
    rows = [
        dict(
            date=day,
            code=code,
            open=100 + drift * i,
            high=101 + drift * i,
            low=99 + drift * i,
            close=100 + drift * i,
            volume=100.0,
        )
        for code, drift in (("US.DEMO_A", 0.5), ("US.DEMO_B", -0.2))
        for i, day in enumerate(dates)
        if not (code == "US.DEMO_A" and i == 6)
    ]
    crypto_dates = [
        (date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(270)
    ]
    prices = dict(
        DEMO_A_USDT=[100 + i / 10 + math.sin(i / 5) for i in range(270)],
        DEMO_B_USDT=[120 - i / 20 + math.cos(i / 7) for i in range(270)],
    )
    return {
        "equity-lab": dict(
            schema="competition.workflow_job.v1",
            project="equity-lab",
            synthetic=True,
            parameters=dict(
                initial_equity=100,
                fee_bps=20,
                quote_currency="USD",
                short_window=3,
                long_window=5,
            ),
            data=dict(dates=dates, rows=rows),
        ),
        "crypto-mm": dict(
            schema="competition.workflow_job.v1",
            project="crypto-mm",
            synthetic=True,
            parameters=dict(
                initial_equity=1,
                fee_bps=35,
                quote_currency="USDT",
                arm_id="trend200_vol40_strict",
                decision_schedule="weekly_monday",
            ),
            data=dict(dates=crypto_dates, close=prices),
        ),
    }


def _csv_matches(path, rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("EMPTY_LEAF_EVIDENCE")
    with safe_path(path).open(encoding="utf-8", newline="") as stream:
        actual = list(csv.DictReader(stream))
    if len(actual) != len(rows):
        raise ValueError("LEAF_TABLE_MISMATCH")
    for expected, record in zip(rows, actual, strict=True):
        for name, value in expected.items():
            if name not in record:
                raise ValueError("LEAF_TABLE_MISMATCH")
            if name in {"date", "code"}:
                same = value == record[name]
            else:
                same = (
                    type(value) in (int, float)
                    and math.isfinite(value)
                    and float(record[name]) == value
                )
            if not same:
                raise ValueError("LEAF_TABLE_MISMATCH")


def validate_leaf_result(run_root: Path, project: str, job: dict, plan: dict) -> dict:
    try:
        if project not in PROJECTS or plan["code"]["source_root"] != "source/source":
            raise ValueError("INVALID_WORKFLOW_PROJECT")
        folder = safe_path(Path(run_root) / project)
        value = _read(folder / "result.json")
        if (
            not isinstance(value, dict)
            or set(value) != FIELDS
            or value["schema"] != "competition.workflow_leaf_result.v1"
            or value["status"] != "completed"
            or value["synthetic"] is not True
            or value["project"] != project
        ):
            raise ValueError("LEAF_IDENTITY_MISMATCH")
        module, model, names = PROJECTS[project]
        package = module.split(".")[0]
        source = Path(run_root) / "source/source/research" / project / "src" / package
        if (
            value["accounting_model"] != model
            or value["parameters"] != job["parameters"]
            or type(value["initial_equity"]) not in (int, float)
            or value["initial_equity"] != job["parameters"]["initial_equity"]
            or value["quote_currency"] != job["parameters"]["quote_currency"]
        ):
            raise ValueError("LEAF_PARAMETERS_MISMATCH")
        if value["input_sha256"] != digest(
            safe_path(Path(run_root) / f"inputs/{project}.json")
        ) or value["code_sha256"] != package_digest(source):
            raise ValueError("LEAF_SOURCE_OR_INPUT_MISMATCH")
        environment = value["environment"]
        if (
            not isinstance(environment, dict)
            or set(environment) != {"python", "distributions"}
            or not isinstance(environment["python"], str)
            or not environment["python"].startswith("3.12.")
            or not isinstance(environment["distributions"], dict)
            or not environment["distributions"]
            or any(
                not isinstance(k, str) or not k or not isinstance(v, str) or not v
                for k, v in environment["distributions"].items()
            )
        ):
            raise ValueError("INVALID_LEAF_ENVIRONMENT")
        records = value["artifacts"]
        if (
            not isinstance(records, list)
            or len(records) != len(names)
            or any(
                not isinstance(r, dict)
                or set(r) != {"path", "sha256", "bytes"}
                or type(r["bytes"]) is not int
                or r["bytes"] < 0
                for r in records
            )
            or {r["path"] for r in records} != set(names)
        ):
            raise ValueError("INVALID_LEAF_ARTIFACTS")
        for record in records:
            path = safe_path(folder / record["path"])
            if (
                not path.is_file()
                or path.stat().st_size != record["bytes"]
                or digest(path) != record["sha256"]
            ):
                raise ValueError("LEAF_ARTIFACT_CHANGED")
        if not isinstance(value["metrics"], dict) or value["metrics"] != _read(
            folder / "summary.json"
        ):
            raise ValueError("LEAF_METRICS_MISMATCH")
        evidence = value["evidence"]
        if project == "crypto-mm":
            if (
                not isinstance(evidence, dict)
                or set(evidence) != {"prices", "net", "gross"}
                or any(evidence[k] != _read(folder / f"{k}.json") for k in evidence)
            ):
                raise ValueError("LEAF_EVIDENCE_MISMATCH")
        else:
            if not isinstance(evidence, dict) or set(evidence) != {
                "portfolio",
                "positions",
                "gross_portfolio",
            }:
                raise ValueError("LEAF_EVIDENCE_MISMATCH")
            for key, name in (
                ("portfolio", "portfolio.csv"),
                ("positions", "positions.csv"),
                ("gross_portfolio", "gross-portfolio.csv"),
            ):
                _csv_matches(folder / name, evidence[key])
        return value
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("INVALID_LEAF_RESULT") from error


def check_workflow_delivery(config, output_root: Path, source_root: Path) -> dict:
    started = time.monotonic()
    source = Path(source_root).absolute()
    if source.resolve() != Path(__file__).resolve().parents[2]:
        raise ValueError("WORKFLOW_MATCHING_SOURCE_CHECKOUT_REQUIRED")
    boundaries = check_boundaries(source)
    if boundaries["status"] != "completed":
        raise ValueError("WORKFLOW_BOUNDARY_CHECK_FAILED")
    if any(not interpreter(config, p).is_file() for p in PROJECTS):
        raise ValueError("WORKFLOW_ENVIRONMENT_UNAVAILABLE")
    run = init_run(output_root)
    (run / "inputs").mkdir()
    jobs = synthetic_jobs()
    for project, job in jobs.items():
        _write(run / f"inputs/{project}.json", job)
    plan = freeze_run(
        source,
        run,
        [f"inputs/{p}.json" for p in jobs],
        dict(
            protocol="synthetic_workflow.v1",
            synthetic=True,
            jobs={p: j["parameters"] for p, j in jobs.items()},
        ),
    )
    (run / "logs").mkdir()
    (run / "explanations").mkdir()
    _write(run / "boundary-check.json", boundaries)
    artifacts = ["boundary-check.json"]
    environments, explained = {"root": dict(python=platform.python_version())}, {}
    try:
        with (run / "attempts.jsonl").open("x", encoding="utf-8") as attempts:
            artifacts.append("attempts.jsonl")
            for project, job in jobs.items():
                if time.monotonic() - started >= 600:
                    raise ValueError("WORKFLOW_TIME_BUDGET")
                attempts.write(
                    json.dumps(
                        dict(project=project, module=PROJECTS[project][0], attempt=1)
                    )
                    + "\n"
                )
                attempts.flush()
                child = run_child(
                    [
                        str(interpreter(config, project)),
                        "-I",
                        "-m",
                        PROJECTS[project][0],
                        "--input",
                        str(run / f"inputs/{project}.json"),
                        "--output-root",
                        str(run / project),
                    ],
                    environment=child_environment(config),
                    timeout=min(180, max(1, int(600 - (time.monotonic() - started)))),
                )
                log_name = f"logs/{project}.log"
                with (run / log_name).open("x", encoding="utf-8") as stream:
                    stream.write(child.stdout + "\n" + child.stderr)
                artifacts.append(log_name)
                if child.returncode != 0:
                    raise ValueError("WORKFLOW_CHILD_FAILED")
                leaf = validate_leaf_result(run, project, job, plan)
                environments[project] = leaf["environment"]
                evidence = leaf["evidence"]
                if project == "equity-lab":
                    explanation = explain_fractional(
                        evidence["portfolio"],
                        evidence["positions"],
                        evidence["gross_portfolio"],
                        initial_equity=leaf["initial_equity"],
                        quote_currency=leaf["quote_currency"],
                    )
                    metric = leaf["metrics"].get("total_return")
                else:
                    explanation = explain_self_financing(
                        evidence["prices"],
                        evidence["net"],
                        evidence["gross"],
                        initial_equity=leaf["initial_equity"],
                    )
                    metric = leaf["metrics"].get("net_return")
                if (
                    type(metric) not in (int, float)
                    or not math.isfinite(metric)
                    or not math.isclose(
                        metric, explanation["net_return"], abs_tol=1e-12, rel_tol=1e-12
                    )
                ):
                    raise ValueError("WORKFLOW_METRICS_UNRECONCILED")
                report = f"explanations/{project}.json"
                _write(run / report, explanation)
                artifacts.extend(
                    [f"{project}/{r['path']}" for r in leaf["artifacts"]]
                    + [f"{project}/result.json", report]
                )
                explained[project] = dict(
                    accounting_model=leaf["accounting_model"],
                    quote_currency=leaf["quote_currency"],
                    periods=explanation["periods"],
                    reconciled=True,
                )
        if source_hash(source) != plan["code"]["source_sha256"]:
            raise ValueError("WORKFLOW_SOURCE_CHANGED")
        if time.monotonic() - started >= 600:
            raise ValueError("WORKFLOW_TIME_BUDGET")
        # This report describes checked outputs. Only the final verified run
        # record establishes completion, so it cannot falsely complete a run.
        _write(
            run / "delivery.json",
            dict(
                schema="competition.workflow_delivery.v1",
                status="outputs_verified",
                synthetic=True,
                accepted_research=False,
                projects=explained,
            ),
        )
        artifacts.append("delivery.json")
        finish_run(run, artifacts, status="completed", environments=environments)
        result = verify_run(run)
        return dict(
            status="completed",
            synthetic=True,
            accepted_research=False,
            projects=2,
            experiment_id=plan["experiment_id"],
            result_sha256=result["result_sha256"],
        )
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        detail = str(error)
        code = (
            "WORKFLOW_TIMEOUT"
            if isinstance(error, subprocess.TimeoutExpired)
            else detail
            if re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", detail)
            else "WORKFLOW_DELIVERY_FAILED"
        )
        # Retain valid partial evidence, but never overwrite or bless a corrupt
        # plan/input. Such failures stay incomplete and the command stays nonzero.
        record_issue = None
        try:
            finish_run(
                run,
                [p for p in artifacts if (run / p).is_file()],
                status="failed",
                environments=environments,
                error_code=code,
            )
        except (ValueError, OSError) as record_error:
            label = str(record_error)
            record_issue = (
                label
                if re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", label)
                else "RUN_FINALIZATION_FAILED"
            )
        return dict(
            status="failed",
            synthetic=True,
            accepted_research=False,
            issue_code=code,
            record_status="incomplete" if record_issue else "failed",
            record_issue=record_issue,
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = check_workflow_delivery(
        load_config(args.config), args.output_root, args.source_root
    )
    print(json.dumps(result, indent=2))
    return int(result["status"] != "completed")


if __name__ == "__main__":
    raise SystemExit(main())
