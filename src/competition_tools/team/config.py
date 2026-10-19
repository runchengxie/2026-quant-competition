"""Explicit, external team configuration without machine-local discovery."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import tomllib

from .paths import validate_external

SCHEMA = "competition.team.v1"


@dataclass(frozen=True)
class TeamConfig:
    data_root: Path
    environment_root: Path


def load_config(path: Path) -> TeamConfig:
    try:
        source = validate_external(path)
        value = tomllib.loads(source.read_text(encoding="utf-8"))
        if set(value) != {"schema_version", "data_root", "environment_root"}:
            raise ValueError("Invalid team configuration keys")
        if value["schema_version"] != SCHEMA:
            raise ValueError("Unsupported team configuration schema")
        paths = [value[key] for key in ("data_root", "environment_root")]
        if any(not isinstance(item, str) or not item.strip() for item in paths):
            raise ValueError("Nonempty absolute paths are required")
        config = TeamConfig(*(validate_external(Path(item)) for item in paths))
        if any(
            p.exists() and not p.is_dir()
            for p in (config.data_root, config.environment_root)
        ):
            raise ValueError("Data and environment roots must be directories")
        return config
    except (OSError, TypeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError("Unable to read team configuration") from exc


def _restrict_file(fd: int, path: Path) -> None:
    if os.name != "nt":
        os.fchmod(fd, 0o600)
        return
    # SID avoids localized account names and never exposes credentials.
    identity = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    import csv

    sid = next(csv.reader(identity.stdout.splitlines()))[1]
    subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", f"*{sid}:(F)"],
        capture_output=True,
        check=True,
        timeout=15,
    )


def init_config(
    path: Path, data_root: Path, environment_root: Path | None = None
) -> TeamConfig:
    destination = validate_external(path)
    data = validate_external(data_root)
    environments = validate_external(
        environment_root or data / "2026-quant-competition/environments"
    )
    if any(p.exists() and not p.is_dir() for p in (data, environments)):
        raise ValueError("Data and environment roots must be directories")
    value = {
        "schema_version": SCHEMA,
        "data_root": str(data),
        "environment_root": str(environments),
    }
    payload = "".join(
        f"{key} = {json.dumps(item, ensure_ascii=True)}\n"
        for key, item in value.items()
    )
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as exc:
        raise ValueError("Unable to create new team configuration") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            _restrict_file(stream.fileno(), destination)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except (OSError, subprocess.SubprocessError, ValueError, IndexError) as exc:
        # Only this exclusive-created file belongs to this attempt.
        destination.unlink(missing_ok=True)
        raise ValueError("Unable to secure team configuration") from exc
    return TeamConfig(data, environments)
