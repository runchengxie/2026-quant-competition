"""Explicit, private single-key migration. Never execute dotenv content."""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib
import uuid

from competition_tools.team.config import _restrict_file
from .dex_spec import safe_path

ASSIGNMENT = re.compile(rb"^[ \t]*(?:export[ \t]+)?DEXPAPRIKA_API_KEY[ \t]*=")


def _restrict_owner(fd, path, *, directory=False):
    if os.name != "nt":
        os.chmod(path, 0o700 if directory else 0o600)
        return
    _restrict_file(fd, path)
    escaped = str(path).replace("'", "''")
    script = (
        "$ErrorActionPreference='Stop'; $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value; "
        "$acl=Get-Acl -LiteralPath '" + escaped + "'; "
        "$foreign=@($acl.Access | ForEach-Object {$_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value} | Where-Object {$_ -ne $sid} | Select-Object -Unique); "
        "ConvertTo-Json -InputObject $foreign -Compress"
    )
    environment = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}
    checked = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-EncodedCommand",
            base64.b64encode(script.encode("utf-16-le")).decode("ascii"),
        ],
        env=environment,
        capture_output=True,
        check=True,
        timeout=30,
    )
    foreign = json.loads(checked.stdout.decode("utf-8-sig"))
    if not isinstance(foreign, list) or any(
        not re.fullmatch(r"S-1-[0-9-]+", sid) for sid in foreign
    ):
        raise ValueError("CREDENTIAL_ACL_INVALID")
    if foreign:
        subprocess.run(
            ["icacls", str(path), "/remove", *["*" + sid for sid in foreign]],
            capture_output=True,
            check=True,
            timeout=30,
        )


def _parse(body: bytes, *, allow_missing: bool = False) -> tuple[str | None, bytes]:
    bom = b"\xef\xbb\xbf" if body.startswith(b"\xef\xbb\xbf") else b""
    lines = body[len(bom) :].splitlines(keepends=True)
    selected = [(i, line) for i, line in enumerate(lines) if ASSIGNMENT.match(line)]
    if len(selected) > 1:
        raise ValueError("DUPLICATE_CREDENTIAL")
    if not selected:
        if allow_missing:
            return None, body
        raise ValueError("INVALID_CREDENTIAL")
    index, line = selected[0]
    try:
        value = line.split(b"=", 1)[1].strip().decode("utf-8")
        if (
            value.startswith(("'", '"'))
            and value.endswith(value[0])
            and len(value) >= 2
        ):
            value = value[1:-1]
        if not re.fullmatch(r"[A-Za-z0-9._~+/=-]+", value):
            raise ValueError
    except (UnicodeError, ValueError):
        raise ValueError("INVALID_CREDENTIAL") from None
    return value, bom + b"".join(lines[:index] + lines[index + 1 :])


def load_key(path: Path) -> str:
    try:
        value, _ = _parse(safe_path(path).read_bytes())
        return value
    except OSError:
        raise ValueError("CREDENTIAL_UNREADABLE") from None


def _secure_write(path: Path, body: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        _restrict_owner(fd, path)
        with os.fdopen(fd, "wb") as stream:
            fd = -1
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if fd != -1:
            os.close(fd)


def _replace_source(path: Path, expected: bytes, replacement: bytes) -> None:
    fd, temporary = tempfile.mkstemp(
        prefix=".env.dexpaprika-", suffix=".tmp", dir=path.parent
    )
    temp = Path(temporary)
    try:
        _restrict_owner(fd, temp)
        with os.fdopen(fd, "wb") as stream:
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
        if safe_path(path, external=False).read_bytes() != expected:
            raise ValueError("SOURCE_CHANGED")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def migrate_key(source_env: Path, destination: Path, workspace: Path) -> dict:
    try:
        settings = tomllib.loads(safe_path(workspace).read_text(encoding="utf-8-sig"))
        code = safe_path(settings["code_root"], external=False)
        config = safe_path(settings["config_root"])
        source = safe_path(source_env, external=False)
        target = safe_path(destination)
        if (
            source != code / "global-market-research/.env"
            or target
            != config / "projects/2026-quant-competition/providers/dexpaprika.env"
        ):
            raise ValueError("INVALID_MIGRATION_PATH")
        before = source.read_bytes()
        key, remaining = _parse(before, allow_missing=True)
        if target.exists():
            existing = load_key(target)
            if key is None:
                _restrict_owner(-1, target.parent, directory=True)
                _restrict_owner(-1, target)
                for recovery in target.parent.glob(".dexpaprika-recovery-*.env"):
                    if re.fullmatch(
                        r"\.dexpaprika-recovery-[a-f0-9]{32}\.env", recovery.name
                    ):
                        _restrict_owner(-1, safe_path(recovery))
                return {"status": "already_migrated"}
            if existing != key:
                raise ValueError("CREDENTIAL_CONFLICT")
        elif key is None:
            raise ValueError("INVALID_CREDENTIAL")
        target.parent.mkdir(parents=True, exist_ok=True)
        # This is the dedicated provider directory, not the shared configuration root.
        _restrict_owner(-1, target.parent, directory=True)
        recovery = target.parent / (".dexpaprika-recovery-" + uuid.uuid4().hex + ".env")
        _secure_write(recovery, before)
        if not target.exists():
            _secure_write(target, ("DEXPAPRIKA_API_KEY=" + key + "\n").encode())
        else:
            _restrict_owner(-1, target)
        if load_key(target) != key:
            raise ValueError("CREDENTIAL_CONFLICT")
        _replace_source(source, before, remaining)
        return {"status": "migrated"}
    except (
        OSError,
        KeyError,
        UnicodeError,
        tomllib.TOMLDecodeError,
        subprocess.SubprocessError,
    ):
        raise ValueError("MIGRATION_INTERRUPTED") from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrate one explicitly named DexPaprika key without exposing it"
    )
    parser.add_argument("operation", choices=["migrate"])
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--source-env", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(
            json.dumps(migrate_key(args.source_env, args.destination, args.workspace))
        )
        return 0
    except ValueError as error:
        print(json.dumps({"status": "blocked", "reason": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
