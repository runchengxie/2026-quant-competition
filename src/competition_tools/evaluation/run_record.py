"""Portable integrity records for explicitly owned offline experiment bundles."""

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from ..datasets.daily_storage import safe_path
from ..datasets.storage import digest
from .controls.source import snapshot_source
from .study_identity import canonical_hash, source_hash

OWNER = "competition.workflow_run.v1"
PLAN = "competition.workflow_plan.v1"
RESULT = "competition.workflow_result.v1"
CONTROL = {".workflow-run", "experiment-plan.json", "experiment-result.json"}
LOCKS = {
    "root": "uv.lock",
    "equity-lab": "research/equity-lab/uv.lock",
    "crypto-mm": "research/crypto-mm/uv.lock",
}


def _write(path, value):
    body = json.dumps(value, indent=2, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def _root(path):
    root = safe_path(Path(path))
    marker = safe_path(root / ".workflow-run")
    if (
        not root.is_dir()
        or not marker.is_file()
        or marker.read_text(encoding="utf-8") != OWNER
    ):
        raise ValueError("INVALID_RUN_OWNER")
    return root


def _member(root, name, *, control=False):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError("INVALID_RUN_PATH")
    relative = PurePosixPath(name)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or str(relative) != name
        or not relative.parts
    ):
        raise ValueError("INVALID_RUN_PATH")
    if not control and (name in CONTROL or relative.parts[0] == "source"):
        raise ValueError("RESERVED_RUN_PATH")
    path = safe_path(root / name)
    if path == root or not path.is_relative_to(root):
        raise ValueError("INVALID_RUN_PATH")
    return path


def _records(root, names):
    if (
        not isinstance(names, list)
        or len(names) > 1024
        or any(not isinstance(n, str) for n in names)
        or len(set(names)) != len(names)
    ):
        raise ValueError("INVALID_RUN_PATH_LIST")
    output = []
    for name in sorted(names):
        path = _member(root, name)
        if not path.is_file():
            raise ValueError("MISSING_RUN_FILE")
        before = path.stat()
        hashed = digest(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("RUN_FILE_CHANGED")
        output.append(dict(path=name, sha256=hashed, bytes=after.st_size))
    return output


def _verify_records(root, records):
    if not isinstance(records, list) or any(
        not isinstance(r, dict)
        or set(r) != {"path", "sha256", "bytes"}
        or type(r["bytes"]) is not int
        or r["bytes"] < 0
        for r in records
    ):
        raise ValueError("INVALID_RUN_FILES")
    if _records(root, [r["path"] for r in records]) != records:
        raise ValueError("RUN_FILES_CHANGED")


def _identity(value):
    code = value["code"]
    return canonical_hash(
        dict(
            code={k: code[k] for k in ("commit", "source_sha256", "lock_sha256")},
            inputs=value["inputs"],
            parameters=value["parameters"],
        )
    )


def _unsigned(value, key):
    return {k: v for k, v in value.items() if k != key}


def init_run(output_root: Path) -> Path:
    output = safe_path(Path(output_root))
    output.mkdir(parents=True, exist_ok=False)
    with (output / ".workflow-run").open("x", encoding="utf-8") as stream:
        stream.write(OWNER)
    return output


def freeze_run(
    source_root: Path, run_root: Path, input_names: list[str], parameters: dict
) -> dict:
    run = _root(run_root)
    if (run / "experiment-plan.json").exists():
        raise FileExistsError("RUN_PLAN_EXISTS")
    if not isinstance(parameters, dict):
        raise ValueError("INVALID_RUN_PARAMETERS")
    parameters = json.loads(json.dumps(parameters, allow_nan=False))
    inputs = _records(run, input_names)
    if not inputs:
        raise ValueError("RUN_INPUTS_REQUIRED")
    receipt = snapshot_source(Path(source_root), run / "source")
    retained = run / "source/source"
    code = dict(
        commit=receipt["commit"],
        source_sha256=receipt["source_sha256"],
        archive="source/source.zip",
        archive_sha256=receipt["archive_sha256"],
        source_root="source/source",
        lock_sha256={name: digest(retained / path) for name, path in LOCKS.items()},
    )
    value = dict(
        schema=PLAN,
        frozen_at=datetime.now(timezone.utc).isoformat(),
        parameters=parameters,
        inputs=inputs,
        code=code,
    )
    value["experiment_id"] = _identity(value)
    value["plan_sha256"] = canonical_hash(value)
    _write(run / "experiment-plan.json", value)
    return value


def _load_plan(root):
    try:
        value = json.loads(
            _member(root, "experiment-plan.json", control=True).read_text(
                encoding="utf-8"
            )
        )
        if (
            set(value)
            != {
                "schema",
                "experiment_id",
                "frozen_at",
                "parameters",
                "inputs",
                "code",
                "plan_sha256",
            }
            or value["schema"] != PLAN
            or not isinstance(value["parameters"], dict)
        ):
            raise ValueError("INVALID_RUN_PLAN")
        if (
            canonical_hash(_unsigned(value, "plan_sha256")) != value["plan_sha256"]
            or _identity(value) != value["experiment_id"]
        ):
            raise ValueError("RUN_PLAN_CHANGED")
        code = value["code"]
        if (
            set(code)
            != {
                "commit",
                "source_sha256",
                "archive",
                "archive_sha256",
                "source_root",
                "lock_sha256",
            }
            or not isinstance(code["commit"], str)
            or not re.fullmatch(r"[0-9a-f]{40,64}", code["commit"])
        ):
            raise ValueError("INVALID_RUN_CODE")
        if (
            code["source_root"] != "source/source"
            or code["archive"] != "source/source.zip"
            or set(code["lock_sha256"]) != set(LOCKS)
        ):
            raise ValueError("INVALID_RUN_CODE_PATH")
        retained = _member(root, code["source_root"], control=True)
        archive = _member(root, code["archive"], control=True)
        if (
            digest(archive) != code["archive_sha256"]
            or source_hash(retained) != code["source_sha256"]
            or any(
                digest(retained / p) != code["lock_sha256"][n] for n, p in LOCKS.items()
            )
        ):
            raise ValueError("RUN_CODE_CHANGED")
        _verify_records(root, value["inputs"])
        return value
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("RUN_PLAN_INCOMPLETE_OR_CHANGED") from error


def finish_run(
    run_root: Path,
    artifact_names: list[str],
    *,
    status: str,
    environments: dict,
    error_code: str | None = None,
) -> dict:
    root = _root(run_root)
    if (root / "experiment-result.json").exists():
        raise FileExistsError("RUN_RESULT_EXISTS")
    plan = _load_plan(root)
    if status not in {"completed", "failed"} or not isinstance(environments, dict):
        raise ValueError("INVALID_RUN_STATUS")
    if (status == "completed" and (error_code is not None or not artifact_names)) or (
        status == "failed"
        and (
            not isinstance(error_code, str)
            or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", error_code)
        )
    ):
        raise ValueError("INVALID_RUN_STATUS")
    artifacts = _records(root, artifact_names)
    if set(artifact_names) & {r["path"] for r in plan["inputs"]}:
        raise ValueError("OVERLAPPING_RUN_PATHS")
    value = dict(
        schema=RESULT,
        plan_sha256=plan["plan_sha256"],
        finished_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        environments=environments,
        artifacts=artifacts,
        error_code=error_code,
    )
    value["result_sha256"] = canonical_hash(value)
    _write(root / "experiment-result.json", value)
    return value


def verify_run(run_root: Path) -> dict:
    root = _root(run_root)
    plan = _load_plan(root)
    try:
        value = json.loads(
            _member(root, "experiment-result.json", control=True).read_text(
                encoding="utf-8"
            )
        )
        if (
            set(value)
            != {
                "schema",
                "plan_sha256",
                "finished_at",
                "status",
                "environments",
                "artifacts",
                "error_code",
                "result_sha256",
            }
            or value["schema"] != RESULT
        ):
            raise ValueError("INVALID_RUN_RESULT")
        if (
            value["plan_sha256"] != plan["plan_sha256"]
            or canonical_hash(_unsigned(value, "result_sha256"))
            != value["result_sha256"]
        ):
            raise ValueError("RUN_RESULT_CHANGED")
        if value["status"] != "completed":
            raise ValueError("RUN_NOT_COMPLETED")
        if (
            value["error_code"] is not None
            or not value["artifacts"]
            or not isinstance(value["environments"], dict)
        ):
            raise ValueError("INVALID_RUN_RESULT")
        _verify_records(root, value["artifacts"])
        if {r["path"] for r in value["artifacts"]} & {
            r["path"] for r in plan["inputs"]
        }:
            raise ValueError("OVERLAPPING_RUN_PATHS")
        return value
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("RUN_RESULT_INCOMPLETE_OR_CHANGED") from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    value = verify_run(parser.parse_args(argv).run_root)
    print(
        json.dumps(dict(status=value["status"], result_sha256=value["result_sha256"]))
    )


if __name__ == "__main__":
    main()
