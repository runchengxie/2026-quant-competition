"""Offline contracts for the Paper-only launch boundary."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from competition_tools import gateway_launcher as gl


def fixture(tmp_path, monkeypatch):
    code, data, private = [tmp_path / n for n in ("code", "data", "private")]
    for root in (code, data, private):
        root.mkdir()
    workspace = tmp_path / "workspace.toml"
    workspace.write_text(
        "\n".join(
            f"{k} = {json.dumps(str(v))}"
            for k, v in [
                ("code_root", code),
                ("data_root", data),
                ("config_root", private),
            ]
        )
    )
    deployment = private / "deployments/2026-quant-competition/ibgateway-paper"
    deployment.mkdir(parents=True)
    tools = private / "tools/ibc"
    tools.mkdir(parents=True)
    archive = tools / "IBCWin-3.24.2.zip"
    upstream = b'@echo off\nset TWS_MAJOR_VRSN=1045\nset CONFIG=old\nset TRADING_MODE=\nset TWOFA_TIMEOUT_ACTION=exit\nset IBC_PATH=old\nset TWS_PATH=old\nset TWS_SETTINGS_PATH=\nset LOG_PATH=old\nset TWSUSERID=\nset TWSPASSWORD=\nset FIXUSERID=\nset FIXPASSWORD=\nset JAVA_PATH=\nset HIDE=\ncall "%IBC_PATH%\\scripts\\DisplayBannerAndLaunch.bat"\n'
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("StartGateway.bat", upstream)
        z.writestr("scripts/DisplayBannerAndLaunch.bat", b"@exit /b 0\n")
        z.writestr("IBC.jar", b"synthetic jar, never executed")
    monkeypatch.setattr(
        gl, "RELEASE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest()
    )
    install = tools / "install"
    install.mkdir()
    with zipfile.ZipFile(archive) as z:
        z.extractall(install)
    gateway = private / "tools/gateway/ibgateway/1050/ibgateway.exe"
    gateway.parent.mkdir(parents=True)
    gateway.write_bytes(b"not executable")
    logs = data / "2026-quant-competition/operations/ibgateway-paper"
    logs.mkdir(parents=True)
    settings = deployment / "settings"
    settings.mkdir()
    ini = deployment / "ibc.ini"
    ini.write_text(
        "TradingMode=paper\nReadOnlyApi=yes\nReadOnlyLogin=no\nExistingSessionDetectedAction=manual\nReloginAfterSecondFactorAuthenticationTimeout=no\nSecondFactorAuthenticationExitInterval=120\nFIX=no\nIbLoginId=PRIVATE_ID\nIbPassword=PRIVATE_SECRET\n"
    )
    cfg = dict(
        schema_version="competition.gateway_launcher.v1",
        ibc_version="3.24.2",
        gateway_version="1050",
        release_archive=str(archive),
        ibc_directory=str(install),
        gateway_executable=str(gateway),
        gateway_sha256=hashlib.sha256(gateway.read_bytes()).hexdigest(),
        ini_path=str(ini),
        settings_directory=str(settings),
        log_directory=str(logs),
        configured_launcher=str(deployment / "StartGateway.paper.bat"),
        activation_authorized=False,
        timeout_seconds=120,
        retry_limit=0,
    )
    path = deployment / "launcher.json"
    path.write_text(json.dumps(cfg))
    return path, workspace, cfg


def build(path, workspace, **kwargs):
    return gl.build_launch_spec(
        path, workspace, acl_probe=lambda p: True, process_probe=lambda: [], **kwargs
    )


def test_valid_dry_run_is_read_only(tmp_path, monkeypatch):
    path, workspace, cfg = fixture(tmp_path, monkeypatch)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    spec = build(path, workspace)
    assert spec["status"] == dict(
        schema_version="competition.gateway_status.v1",
        state="preflight_passed",
        mode="paper",
        read_only_api=True,
        activation_authorized=False,
        authentication="not_checked",
        api="not_checked",
        historical_data="not_checked",
    )
    assert "PRIVATE_" not in json.dumps(spec)
    assert not Path(cfg["configured_launcher"]).exists()
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


def test_verified_archive_shortcut_names_survive_prepare_and_recheck(tmp_path, monkeypatch):
    path, workspace, cfg = fixture(tmp_path, monkeypatch)
    archive = Path(cfg["release_archive"])
    with zipfile.ZipFile(archive, "a") as release:
        for name in ("IBC (Gateway).lnk", "IBC (TWS).lnk"):
            release.writestr(name, b"synthetic shortcut, never executed")
            (Path(cfg["ibc_directory"]) / name).write_bytes(
                b"synthetic shortcut, never executed"
            )
    monkeypatch.setattr(gl, "RELEASE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest())
    gl.prepare_launcher(build(path, workspace))
    assert build(path, workspace)["launcher_ready"]
    shortcut = Path(cfg["configured_launcher"]).parent / "runtime/IBC (Gateway).lnk"
    shortcut.write_bytes(b"tampered")
    with pytest.raises(gl.LauncherError, match="RUNTIME_INTEGRITY_FAILED"):
        build(path, workspace)


@pytest.mark.parametrize(
    "line",
    [
        "TradingMode=live",
        "ReadOnlyApi=no",
        "ReadOnlyLogin=yes",
        "ExistingSessionDetectedAction=primaryoverride",
        "ReloginAfterSecondFactorAuthenticationTimeout=yes",
        "FIX=yes",
    ],
)
def test_unsafe_ini_rejected(tmp_path, monkeypatch, line):
    path, workspace, cfg = fixture(tmp_path, monkeypatch)
    ini = Path(cfg["ini_path"])
    key = line.split("=")[0]
    ini.write_text(
        "\n".join(
            line if row.startswith(key + "=") else row
            for row in ini.read_text().splitlines()
        )
    )
    with pytest.raises(gl.LauncherError, match="UNSAFE_IBC_CONFIGURATION"):
        build(path, workspace)


def test_missing_mode_and_duplicate_keys_rejected(tmp_path, monkeypatch):
    path, workspace, cfg = fixture(tmp_path, monkeypatch)
    ini = Path(cfg["ini_path"])
    original = ini.read_text()
    for content in (
        original.replace("TradingMode=paper\n", ""),
        original + "\ntradingmode=paper",
    ):
        ini.write_text(content)
        with pytest.raises(gl.LauncherError):
            build(path, workspace)


@pytest.mark.parametrize(
    "field,value",
    [
        ("retry_limit", 1),
        ("timeout_seconds", True),
        ("timeout_seconds", 0),
        ("gateway_version", "1045"),
        ("ibc_version", "3.24.1"),
        ("ini_path", "relative.ini"),
        ("gateway_sha256", "a" * 64),
        ("activation_authorized", "yes"),
    ],
)
def test_invalid_config(tmp_path, monkeypatch, field, value):
    path, workspace, cfg = fixture(tmp_path, monkeypatch)
    cfg[field] = value
    path.write_text(json.dumps(cfg))
    with pytest.raises(gl.LauncherError):
        build(path, workspace)


def test_acl_and_existing_process_fail_closed(tmp_path, monkeypatch):
    path, workspace, _ = fixture(tmp_path, monkeypatch)
    with pytest.raises(gl.LauncherError, match="UNSAFE_ACL"):
        gl.build_launch_spec(
            path, workspace, acl_probe=lambda p: False, process_probe=lambda: []
        )
    with pytest.raises(gl.LauncherError, match="EXISTING_GATEWAY_OR_JAVA"):
        gl.build_launch_spec(
            path, workspace, acl_probe=lambda p: True, process_probe=lambda: ["javaw"]
        )


def test_mutated_release_or_runtime_rejected(tmp_path, monkeypatch):
    path, workspace, cfg = fixture(tmp_path, monkeypatch)
    script = Path(cfg["ibc_directory"]) / "scripts/DisplayBannerAndLaunch.bat"
    script.write_text("@echo PRIVATE_SECRET")
    with pytest.raises(gl.LauncherError, match="IBC_INTEGRITY_FAILED"):
        build(path, workspace)
    Path(cfg["release_archive"]).write_bytes(b"changed")
    with pytest.raises(gl.LauncherError, match="IBC_INTEGRITY_FAILED"):
        build(path, workspace)


def test_configured_launcher_is_exact_reviewed_transformation(tmp_path, monkeypatch):
    path, workspace, cfg = fixture(tmp_path, monkeypatch)
    spec = build(path, workspace)
    gl.prepare_launcher(spec)
    assert "set TRADING_MODE=paper" in Path(cfg["configured_launcher"]).read_text()
    assert "PRIVATE_SECRET" not in Path(cfg["configured_launcher"]).read_text()
    assert build(path, workspace)["launcher_ready"] is True
    Path(cfg["configured_launcher"]).write_text("@echo off\nset TRADING_MODE=live")
    with pytest.raises(gl.LauncherError, match="CONFIGURED_LAUNCHER_MISMATCH"):
        build(path, workspace)


def test_cli_help_and_errors_redact(tmp_path):
    help_result = subprocess.run(
        [sys.executable, "-m", "competition_tools.gateway_launcher", "--help"],
        capture_output=True,
        text=True,
    )
    assert help_result.returncode == 0
    for args in (
        ["--PRIVATE_SECRET"],
        [
            "check",
            "--config",
            str(tmp_path / "PRIVATE_SECRET"),
            "--workspace",
            str(tmp_path / "missing"),
        ],
    ):
        result = subprocess.run(
            [sys.executable, "-m", "competition_tools.gateway_launcher", *args],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "PRIVATE_SECRET" not in result.stdout + result.stderr
        assert "Traceback" not in result.stdout + result.stderr
        assert json.loads(result.stdout)["state"] == "blocked"


def test_private_runtime_removes_upstream_retry_and_install_rename(
    tmp_path, monkeypatch
):
    path, workspace, cfg = fixture(tmp_path, monkeypatch)
    original = (
        '@echo off\n:startIBC\nif exist "%PROGRAM_PATH%\\tws.exe" (\nren tws.exe tws1.exe\n)\n'
        'if exist "%PROGRAM_PATH%\\ibgateway.exe" (\nren ibgateway.exe ibgateway1.exe\n)\n'
        "echo.\n\n:: temporarily change the current working directory\n"
        "echo launch\ngoto :startIBC\n:NormalExit\nexit /B %ERRORLEVEL%\n"
    )
    archive = Path(cfg["release_archive"])
    with zipfile.ZipFile(archive, "a") as z:
        z.writestr("scripts/StartIBC.bat", original)
    (Path(cfg["ibc_directory"]) / "scripts/StartIBC.bat").write_bytes(original.encode())
    monkeypatch.setattr(
        gl, "RELEASE_SHA256", hashlib.sha256(archive.read_bytes()).hexdigest()
    )
    spec = build(path, workspace)
    gl.prepare_launcher(spec)
    generated = Path(cfg["configured_launcher"]).parent / "runtime/scripts/StartIBC.bat"
    text = generated.read_text()
    assert "goto :startIBC" not in text
    assert "ren tws.exe" not in text
    assert "ren ibgateway.exe" not in text
    assert "goto :NormalExit" in text
    assert (Path(cfg["ibc_directory"]) / "scripts/StartIBC.bat").read_text() == original
    assert build(path, workspace)["start_supported"] is True
    generated.write_text("@echo tampered")
    with pytest.raises(gl.LauncherError, match="RUNTIME_INTEGRITY_FAILED"):
        build(path, workspace)


@pytest.mark.parametrize(
    "addition",
    [
        r"ReadOnly\u0041pi=no",
        r"ExistingSessionDetected\u0041ction=primaryoverride",
        "OverrideTwsApiPort=7496",
        "AcceptIncomingConnectionAction=accept",
        "AccessToken=SYNTHETIC_SECRET_SENTINEL",
        "IbPasswrod=SYNTHETIC_SECRET_SENTINEL",
        ";AccessToken=SYNTHETIC_SECRET_SENTINEL",
        "\u00a0IbPassword=SYNTHETIC_SECRET_SENTINEL",
    ],
)
def test_unreviewed_properties_never_reach_ibc_logs(tmp_path, monkeypatch, addition):
    path, workspace, cfg = fixture(tmp_path, monkeypatch)
    with Path(cfg["ini_path"]).open("a", encoding="utf-8") as stream:
        stream.write("\n" + addition + "\n")
    with pytest.raises(gl.LauncherError, match="UNSAFE_IBC_CONFIGURATION"):
        build(path, workspace)


def test_properties_case_and_credential_continuation_rejected(tmp_path, monkeypatch):
    path, workspace, cfg = fixture(tmp_path, monkeypatch)
    ini = Path(cfg["ini_path"])
    original = ini.read_text()
    for content in (
        original.replace("ReadOnlyApi=yes", "readonlyapi=yes"),
        original.replace(
            "ReadOnlyApi=yes", "IbPassword=SENTINEL\\\nReadOnlyApi=yes"
        ).replace("IbPassword=PRIVATE_SECRET\n", ""),
    ):
        ini.write_text(content)
        with pytest.raises(gl.LauncherError, match="UNSAFE_IBC_CONFIGURATION"):
            build(path, workspace)


def test_prepare_filesystem_failures_are_redacted(tmp_path, monkeypatch, capsys):
    path, workspace, cfg = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(gl, "owner_only_acl", lambda p: True)
    monkeypatch.setattr(gl, "gateway_processes", lambda: [])
    args = ["prepare", "--config", str(path), "--workspace", str(workspace)]
    assert gl.main(args) == 0
    capsys.readouterr()
    assert gl.main(args) == 2
    output = capsys.readouterr()
    assert json.loads(output.out)["code"] == "PREPARATION_FAILED"
    assert str(tmp_path) not in output.out + output.err
    # A blocked write must use the same public error boundary.
    cached_spec = build(path, workspace)
    monkeypatch.setattr(gl, "build_launch_spec", lambda *a: cached_spec)
    monkeypatch.setattr(
        gl,
        "prepare_launcher",
        lambda spec: (_ for _ in ()).throw(PermissionError("PRIVATE_SECRET")),
    )
    assert gl.main(args) == 2
    assert "PRIVATE_SECRET" not in str(capsys.readouterr())
