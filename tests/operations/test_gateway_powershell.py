"""Native PowerShell wrapper tests use synthetic children only."""

import json
import os
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="Native PowerShell tests run in Windows CI"
)
ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "operations/windows/PaperGateway.psm1"
WRAPPER = ROOT / "operations/windows/Start-PaperGateway.ps1"


def run(script, tmp_path):
    path = tmp_path / "test.ps1"
    path.write_text(script, encoding="utf-8")
    return subprocess.run(
        ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(path)],
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_check_never_starts_child(tmp_path):
    result = run(
        f"""
Import-Module '{MODULE}' -Force
$probe={{param($action) @{{status=@{{state='preflight_passed'}}}}}}
$result=Invoke-PaperGateway -Action check -SpecProbe $probe
$result | ConvertTo-Json -Compress
""",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state"] == "preflight_passed"


def test_child_exit_and_private_output(tmp_path):
    child = tmp_path / "fake.bat"
    child.write_text("@echo PRIVATE_SECRET\n@exit /b 7\n")
    result = run(
        f"""
Import-Module '{MODULE}' -Force
$probe={{param($action) @{{config=@{{configured_launcher='{child}';log_directory='{tmp_path}';timeout_seconds=3;activation_authorized=$true}};launcher_sha256=(Get-FileHash -LiteralPath '{child}').Hash.ToLowerInvariant()}}}}
$result=Invoke-PaperGateway -Action start -SpecProbe $probe -InteractiveProbe {{$true}}
$result | ConvertTo-Json -Compress
""",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert value["exit_code"] == 7
    assert value["state"] == "child_exited"
    assert "PRIVATE_SECRET" not in result.stdout + result.stderr
    assert list(tmp_path.glob("launcher-*.stdout.log"))


def test_noninteractive_start_blocked(tmp_path):
    result = run(
        f"""
Import-Module '{MODULE}' -Force
Invoke-PaperGateway -Action start -SpecProbe {{throw 'PRIVATE_SECRET'}} -InteractiveProbe {{$false}} | ConvertTo-Json -Compress
""",
        tmp_path,
    )
    assert json.loads(result.stdout)["code"] == "INTERACTIVE_DESKTOP_REQUIRED"
    assert "PRIVATE_SECRET" not in result.stdout + result.stderr


def test_public_wrapper_argument_errors_redacted(tmp_path):
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(WRAPPER), "--PRIVATE_SECRET"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    assert "PRIVATE_SECRET" not in result.stdout + result.stderr
    assert json.loads(result.stdout)["code"] == "INVALID_ARGUMENTS"


def test_task_xml_is_unregistered_interactive_and_external(tmp_path):
    artifact = tmp_path / "task.xml"
    stable = tmp_path / "deployed"
    stable.mkdir()
    wrapper = stable / "Start-PaperGateway.ps1"
    wrapper.write_text("# synthetic only")
    result = run(
        f"""
Import-Module '{MODULE}' -Force
Export-PaperGatewayTask -OutputPath '{artifact}' -WrapperPath '{wrapper}' -PythonPath 'C:/Python/python.exe' -ConfigPath '{tmp_path}/launcher.json' -WorkspacePath '{tmp_path}/workspace.toml' -UserSid 'S-1-5-21-123-456-789-1001'
""",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    import xml.etree.ElementTree as ET

    root = ET.parse(artifact).getroot()
    ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    for query, expected in (
        (".//t:LogonType", "InteractiveToken"),
        (".//t:RunLevel", "LeastPrivilege"),
        (".//t:Settings/t:Enabled", "false"),
    ):
        element = root.find(query, ns)
        assert element is not None
        assert element.text == expected
    assert root.find(".//t:RestartOnFailure", ns) is None
    assert "Password" not in artifact.read_text()
