"""Fail-closed, non-secret specification for a separately activated Paper launcher.

Only prepare writes files. No Python command starts/stops Gateway or opens a socket.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tomllib
import zipfile

RELEASE_SHA256 = "ba8e95f61f3c7c252620baef41e550c6aab98f6034179156e11a9a1623fdd892"
KEYS = set(
    "schema_version ibc_version gateway_version release_archive ibc_directory gateway_executable gateway_sha256 ini_path settings_directory log_directory configured_launcher activation_authorized timeout_seconds retry_limit".split()
)
UNSAFE_PATH = re.compile(r'[\x00-\x1f"%!&|<>^()]')


class LauncherError(ValueError):
    """Contains a stable code only, never input text or private paths."""


def fail(code):
    raise LauncherError(code)


def _path(value, *, exists=True):
    if not isinstance(value, str) or UNSAFE_PATH.search(value):
        fail("INVALID_PATH")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        fail("INVALID_PATH")
    for parent in (path, *path.parents):
        if parent.is_symlink() or (
            hasattr(parent, "is_junction") and parent.is_junction()
        ):
            fail("REPARSE_PATH")
    if exists and not path.exists():
        fail("REQUIRED_PATH_MISSING")
    return path.resolve()


def _inside(path, root):
    if path == root or not path.is_relative_to(root):
        fail("PATH_OUTSIDE_OWNER_ROOT")


def _sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail("DUPLICATE_KEY")
        result[key] = value
    return result


def _powershell(script, **env):
    if os.name != "nt":
        fail("WINDOWS_REQUIRED")
    result = subprocess.run(
        [
            "pwsh",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); "
            + script,
        ],
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        fail("PROBE_FAILED")
    return result.stdout.strip()


def owner_only_acl(path):
    """Accept owner/SYSTEM allow entries only, including inherited entries."""
    return (
        _powershell(
            "$a=Get-Acl -LiteralPath $env:QC_ACL_PATH; "
            "$me=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value; "
            "$owner=$a.GetOwner([Security.Principal.SecurityIdentifier]).Value; "
            "$ok=$owner -eq $me; "
            "foreach($r in $a.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier])) { "
            "if($r.AccessControlType -eq 'Allow' -and $r.IdentityReference.Value -notin @($me,'S-1-5-18')) {$ok=$false} }; "
            "if($ok){'true'}else{'false'}",
            QC_ACL_PATH=str(path),
        )
        == "true"
    )


def gateway_processes():
    # Java cannot safely be attributed without reading command lines. Any Java blocks launch.
    result = _powershell(
        "@(Get-Process -ErrorAction Stop | Where-Object { $_.ProcessName -match '^(ibgateway|ibgateway1|tws|tws1|java|javaw)$' } | ForEach-Object {$_.ProcessName}) | ConvertTo-Json -Compress"
    )
    if not result:
        return []
    parsed = json.loads(result)
    return [parsed] if isinstance(parsed, str) else parsed


def _ini(path, timeout):
    # Credentials are ignored; the parser never returns or logs their values.
    values = {}
    for row in path.read_text(encoding="utf-8-sig").splitlines():
        row = row.strip()
        if not row or row.startswith(("#", ";")):
            continue
        if "=" not in row:
            fail("UNSAFE_IBC_CONFIGURATION")
        key, value = row.split("=", 1)
        key = key.strip().casefold()
        if key in values:
            fail("DUPLICATE_KEY")
        values[key] = value.strip().casefold()
    required = dict(
        tradingmode="paper",
        readonlyapi="yes",
        readonlylogin="no",
        existingsessiondetectedaction={"manual", "secondary"},
        reloginaftersecondfactorauthenticationtimeout="no",
        fix="no",
    )
    for key, expected in required.items():
        if values.get(key) not in (
            expected if isinstance(expected, set) else {expected}
        ):
            fail("UNSAFE_IBC_CONFIGURATION")
    interval = values.get("secondfactorauthenticationexitinterval", "")
    if (
        not interval.isascii()
        or not interval.isdecimal()
        or not 1 <= int(interval) <= timeout
    ):
        fail("UNSAFE_IBC_CONFIGURATION")
    # No restarts, remote command server, trusted-IP changes or automatic API acknowledgement.
    for key in (
        "autorestarttime",
        "coldrestarttime",
        "closedowntime",
        "ibdir",
        "trustedtwsapi clientips".replace(" ", ""),
    ):
        if values.get(key):
            fail("UNSAFE_IBC_CONFIGURATION")
    if values.get("commandserverport", "0") not in {"", "0"}:
        fail("UNSAFE_IBC_CONFIGURATION")


def _archive(config):
    path, install = Path(config["release_archive"]), Path(config["ibc_directory"])
    if _sha(path) != RELEASE_SHA256:
        fail("IBC_INTEGRITY_FAILED")
    contents = {}
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            name = PurePosixPath(entry.filename)
            if (
                name.is_absolute()
                or ".." in name.parts
                or "\\" in entry.filename
                or ":" in entry.filename
            ):
                fail("IBC_INTEGRITY_FAILED")
            if entry.is_dir():
                continue
            if entry.filename in contents or entry.file_size > 10_000_000:
                fail("IBC_INTEGRITY_FAILED")
            contents[entry.filename] = archive.read(entry)
            # Upstream config.ini is a demo file, never the authoritative private config.
            actual = _path(str(install.joinpath(*name.parts)))
            if not actual.is_file() or actual.read_bytes() != contents[entry.filename]:
                fail("IBC_INTEGRITY_FAILED")
    if (
        not {"StartGateway.bat", "scripts/DisplayBannerAndLaunch.bat", "IBC.jar"}
        <= contents.keys()
    ):
        fail("IBC_INTEGRITY_FAILED")
    # Additional scripts/jars could execute through upstream wildcard discovery.
    actual_files = {
        p.relative_to(install).as_posix() for p in install.rglob("*") if p.is_file()
    }
    if actual_files != contents.keys():
        fail("IBC_INTEGRITY_FAILED")
    return contents


def _launcher_bytes(original, config):
    replacements = dict(
        TWS_MAJOR_VRSN="1050",
        CONFIG=config["ini_path"],
        TRADING_MODE="paper",
        TWOFA_TIMEOUT_ACTION="exit",
        IBC_PATH=str(Path(config["configured_launcher"]).parent / "runtime"),
        TWS_PATH=str(Path(config["gateway_executable"]).parents[2]),
        TWS_SETTINGS_PATH=config["settings_directory"],
        LOG_PATH=config["log_directory"],
        TWSUSERID="",
        TWSPASSWORD="",
        FIXUSERID="",
        FIXPASSWORD="",
        JAVA_PATH="",
        HIDE="",
    )
    text = original.decode("utf-8-sig")
    for key, value in replacements.items():
        text, count = re.subn(
            rf"(?im)^set {key}=[^\r\n]*", lambda _: f"set {key}={value}", text
        )
        if count != 1:
            fail("UNSUPPORTED_UPSTREAM_LAUNCHER")
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")


def _runtime(contents):
    """Derive a private bounded runtime; original release remains byte-for-byte intact."""
    result = dict(contents)
    name = "scripts/StartIBC.bat"
    if name in result:
        text = result[name].decode("utf-8-sig").replace("\r\n", "\n")
        start = text.find('if exist "%PROGRAM_PATH%\\tws.exe" (')
        end = text.find(":: temporarily change the current working directory", start)
        if start < 0 or end < 0 or "ibgateway.exe" not in text[start:end]:
            fail("UNSUPPORTED_UPSTREAM_LAUNCHER")
        text = text[:start] + text[end:]
        if "goto :startIBC" not in text:
            fail("UNSUPPORTED_UPSTREAM_LAUNCHER")
        text = text.replace("goto :startIBC", "goto :NormalExit")
        result[name] = text.replace("\n", "\r\n").encode("utf-8")
    name = "scripts/DisplayBannerAndLaunch.bat"
    # Preserve upstream error codes without waiting on a hidden console prompt.
    result[name] = result[name].replace(b"pause > NUL", b"exit /B %ERRORCODE%")
    return result


def build_launch_spec(
    config_path, workspace_path, *, acl_probe=None, process_probe=None
):
    """Read-only validation. Injected probes are for unit callers, never CLI flags."""
    acl_probe = owner_only_acl if acl_probe is None else acl_probe
    process_probe = gateway_processes if process_probe is None else process_probe
    try:
        workspace = tomllib.loads(
            _path(str(workspace_path)).read_text(encoding="utf-8-sig")
        )
        roots = {
            key: _path(workspace[key])
            for key in ("code_root", "data_root", "config_root")
        }
        deployment = (
            roots["config_root"] / "deployments/2026-quant-competition/ibgateway-paper"
        )
        path = _path(str(config_path))
        _inside(path, deployment)
        if path.is_relative_to(roots["code_root"]):
            fail("PRIVATE_CONFIG_IN_SOURCE")
        if not acl_probe(deployment) or not acl_probe(path):
            fail("UNSAFE_ACL")
        config = json.loads(
            path.read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs
        )
        if not isinstance(config, dict) or set(config) != KEYS:
            fail("INVALID_CONFIGURATION")
        if (
            config["schema_version"] != "competition.gateway_launcher.v1"
            or config["ibc_version"] != "3.24.2"
            or config["gateway_version"] != "1050"
        ):
            fail("UNSUPPORTED_VERSION")
        if (
            type(config["activation_authorized"]) is not bool
            or type(config["retry_limit"]) is not int
            or config["retry_limit"] != 0
        ):
            fail("INVALID_CONFIGURATION")
        if (
            type(config["timeout_seconds"]) is not int
            or not 30 <= config["timeout_seconds"] <= 300
        ):
            fail("INVALID_CONFIGURATION")
        for key in (
            "release_archive",
            "ibc_directory",
            "gateway_executable",
            "ini_path",
            "settings_directory",
            "log_directory",
            "configured_launcher",
        ):
            config[key] = str(_path(config[key], exists=key != "configured_launcher"))
        for key in ("ini_path", "settings_directory", "configured_launcher"):
            _inside(Path(config[key]), deployment)
        _inside(
            Path(config["log_directory"]),
            roots["data_root"] / "2026-quant-competition/operations",
        )
        for key in (
            "release_archive",
            "ibc_directory",
            "gateway_executable",
            "ini_path",
            "settings_directory",
            "log_directory",
        ):
            if Path(config[key]).is_relative_to(roots["code_root"]):
                fail("PRIVATE_CONFIG_IN_SOURCE")
        for key in ("ini_path", "settings_directory", "log_directory"):
            if not acl_probe(Path(config[key])):
                fail("UNSAFE_ACL")
        for key in ("release_archive", "ibc_directory", "gateway_executable"):
            if not acl_probe(Path(config[key]).parent) or not acl_probe(
                Path(config[key])
            ):
                fail("UNSAFE_ACL")
        if (
            not re.fullmatch("[0-9a-f]{64}", config["gateway_sha256"])
            or _sha(Path(config["gateway_executable"])) != config["gateway_sha256"]
        ):
            fail("GATEWAY_INTEGRITY_FAILED")
        exe = Path(config["gateway_executable"])
        if (
            exe.name.lower() != "ibgateway.exe"
            or exe.parent.name != "1050"
            or exe.parent.parent.name.lower() != "ibgateway"
        ):
            fail("UNSUPPORTED_GATEWAY_LAYOUT")
        _ini(Path(config["ini_path"]), config["timeout_seconds"])
        contents = _archive(config)
        runtime = _runtime(contents)
        runtime_path = Path(config["configured_launcher"]).parent / "runtime"
        if runtime_path.exists():
            if not acl_probe(runtime_path):
                fail("UNSAFE_ACL")
            for name, content in runtime.items():
                actual = _path(str(runtime_path.joinpath(*PurePosixPath(name).parts)))
                if not actual.is_file() or actual.read_bytes() != content:
                    fail("RUNTIME_INTEGRITY_FAILED")
            if {
                p.relative_to(runtime_path).as_posix()
                for p in runtime_path.rglob("*")
                if p.is_file()
            } != runtime.keys():
                fail("RUNTIME_INTEGRITY_FAILED")
        expected = _launcher_bytes(contents["StartGateway.bat"], config)
        launcher = Path(config["configured_launcher"])
        if launcher.exists() and (
            not acl_probe(launcher) or launcher.read_bytes() != expected
        ):
            fail("CONFIGURED_LAUNCHER_MISMATCH")
        if process_probe():
            fail("EXISTING_GATEWAY_OR_JAVA")
        status = dict(
            schema_version="competition.gateway_status.v1",
            state="preflight_passed",
            mode="paper",
            read_only_api=True,
            activation_authorized=config["activation_authorized"],
            authentication="not_checked",
            api="not_checked",
            historical_data="not_checked",
        )
        start_supported = "scripts/StartIBC.bat" in runtime and runtime_path.exists()
        return dict(
            status=status,
            config=config,
            launcher_ready=launcher.exists(),
            launcher_sha256=hashlib.sha256(expected).hexdigest(),
            launcher_content=expected.decode("utf-8"),
            start_supported=start_supported,
            runtime_files={name: content.hex() for name, content in runtime.items()},
        )
    except LauncherError:
        raise
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        zipfile.BadZipFile,
        subprocess.SubprocessError,
    ):
        fail("CONFIGURATION_OR_PROBE_FAILED")


def prepare_launcher(spec):
    """Create only a new configured wrapper; never overwrite an existing installation."""
    path = Path(spec["config"]["configured_launcher"])
    runtime = path.parent / "runtime"
    runtime.mkdir(exist_ok=False)
    for name, content in spec["runtime_files"].items():
        target = runtime.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(bytes.fromhex(content))
    with path.open("xb") as stream:
        stream.write(spec["launcher_content"].encode("utf-8"))


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        fail("INVALID_ARGUMENTS")


def main(argv=None):
    try:
        parser = SafeParser(
            description="Validate a Paper-only launcher without starting Gateway."
        )
        parser.add_argument(
            "action", choices=("check", "dry-run", "status", "prepare", "launch-spec")
        )
        parser.add_argument("--config", required=True)
        parser.add_argument("--workspace", required=True)
        args = parser.parse_args(argv)
        spec = build_launch_spec(args.config, args.workspace)
        if args.action == "prepare":
            prepare_launcher(spec)
        if args.action == "launch-spec":
            if not spec["status"]["activation_authorized"]:
                fail("ACTIVATION_NOT_AUTHORIZED")
            if not spec["start_supported"]:
                fail("UPSTREAM_RETRY_POLICY_UNSUPPORTED")
            if not spec["launcher_ready"]:
                fail("LAUNCHER_NOT_PREPARED")
            # Non-secret local specification, captured privately by the PowerShell wrapper.
            print(json.dumps({k: spec[k] for k in ("config", "launcher_sha256")}))
        else:
            print(json.dumps(spec["status"]))
        return 0
    except LauncherError as exc:
        print(
            json.dumps(
                dict(
                    schema_version="competition.gateway_status.v1",
                    state="blocked",
                    code=str(exc),
                )
            )
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
