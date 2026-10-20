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
        encoding="utf-8",
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


def test_ensure_ready_skips_launch_checks_even_without_desktop(tmp_path):
    result = run(
        f"""
Import-Module '{MODULE}' -Force
Invoke-PaperGateway -Action ensure -ApiProbe {{@{{state='ready'}}}} -SpecProbe {{throw 'must not launch'}} -InteractiveProbe {{$false}} | ConvertTo-Json -Compress
""",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state"] == "api_ready"
    assert not (tmp_path / "launch.lease").exists()


def test_ensure_starts_once_then_checks_api_and_releases_known_ready_lease(tmp_path):
    child = tmp_path / "fake.bat"
    child.write_text("@echo PRIVATE_SENTINEL\n@ping -n 5 127.0.0.1 >nul\n")
    result = run(
        f"""
Import-Module '{MODULE}' -Force
$script:checks=0
$api={{ $script:checks++; if($script:checks -ge 3) {{@{{state='ready'}}}} else {{@{{state='not_ready'}}}} }}
$probe={{param($action) @{{config=@{{configured_launcher='{child}';log_directory='{tmp_path}';timeout_seconds=5;activation_authorized=$true}};launcher_sha256=(Get-FileHash -LiteralPath '{child}').Hash.ToLowerInvariant()}}}}
$result=Invoke-PaperGateway -Action ensure -SpecProbe $probe -ApiProbe $api -InteractiveProbe {{$true}}
$result|ConvertTo-Json -Compress
""",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state"] == "api_ready"
    assert len(list(tmp_path.glob("launcher-*.stdout.log"))) == 1
    assert not (tmp_path / "launch.lease").exists()
    assert "PRIVATE_SENTINEL" not in result.stdout + result.stderr


def test_ensure_timeout_keeps_lease_and_never_relaunches(tmp_path):
    child = tmp_path / "fake.bat"
    child.write_text("@ping -n 4 127.0.0.1 >nul\n")
    value = run(
        f"""
Import-Module '{MODULE}' -Force
$probe={{param($action) @{{config=@{{configured_launcher='{child}';log_directory='{tmp_path}';timeout_seconds=1;activation_authorized=$true}};launcher_sha256=(Get-FileHash -LiteralPath '{child}').Hash.ToLowerInvariant()}}}}
Invoke-PaperGateway -Action ensure -SpecProbe $probe -ApiProbe {{@{{state='not_ready'}}}} -InteractiveProbe {{$true}} | ConvertTo-Json -Compress
""",
        tmp_path,
    )
    assert value.returncode == 0, value.stderr
    assert json.loads(value.stdout)["exit_code"] == 3
    assert (tmp_path / "launch.lease").exists()
    assert len(list(tmp_path.glob("launcher-*.stdout.log"))) == 1


def test_ensure_rejects_late_ready_and_retains_lease(tmp_path):
    child = tmp_path / "fake.bat"
    child.write_text("@ping -n 6 127.0.0.1 >nul\n")
    value = run(
        f"""
Import-Module '{MODULE}' -Force
$script:checks=0
$api={{$script:checks++; if($script:checks -eq 1) {{@{{state='not_ready'}}}} else {{Start-Sleep -Seconds 3; @{{state='ready'}}}}}}
$probe={{param($action) @{{config=@{{configured_launcher='{child}';log_directory='{tmp_path}';timeout_seconds=2;activation_authorized=$true}};launcher_sha256=(Get-FileHash -LiteralPath '{child}').Hash.ToLowerInvariant()}}}}
Invoke-PaperGateway -Action ensure -SpecProbe $probe -ApiProbe $api -InteractiveProbe {{$true}} | ConvertTo-Json -Compress
""",
        tmp_path,
    )
    assert value.returncode == 0, value.stderr
    assert json.loads(value.stdout)["state"] == "observation_timeout"
    assert (tmp_path / "launch.lease").exists()
    assert len(list(tmp_path.glob("launcher-*.stdout.log"))) == 1


def test_probe_process_deadline_stops_only_probe(tmp_path):
    slow = tmp_path / "slow.py"
    slow.write_text("import time\ntime.sleep(10)\nprint('PRIVATE_SENTINEL')\n")
    import sys

    value = run(
        f"""
Import-Module '{MODULE}' -Force
$clock=[Diagnostics.Stopwatch]::StartNew()
$result=& (Get-Module PaperGateway) {{param($python,$script)
    Invoke-PaperApiProbe -PythonPath $python -Arguments @($script) -BudgetSeconds 1
}} '{sys.executable}' '{slow}'
@{{result=$result;elapsed=$clock.Elapsed.TotalSeconds}} | ConvertTo-Json -Compress
""",
        tmp_path,
    )
    assert value.returncode == 0, value.stderr
    payload = json.loads(value.stdout)
    assert payload["result"]["code"] == "API_PROBE_TIMEOUT"
    assert payload["elapsed"] < 5
    assert "PRIVATE_SENTINEL" not in value.stdout + value.stderr


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


def test_concurrent_starts_and_timeout_hold_launch_lease(tmp_path):
    child = tmp_path / "slow.bat"
    marker = tmp_path / "children.txt"
    child.write_text(
        f'@echo child>>"{marker}"\n@ping -n 5 127.0.0.1 >nul\n@exit /b 0\n'
    )
    script = f"""
Import-Module '{MODULE}' -Force
$probe={{param($action) @{{config=@{{configured_launcher='{child}';log_directory='{tmp_path}';timeout_seconds=1;activation_authorized=$true}};launcher_sha256=(Get-FileHash -LiteralPath '{child}').Hash.ToLowerInvariant()}}}}
Invoke-PaperGateway -Action start -SpecProbe $probe -InteractiveProbe {{$true}} | ConvertTo-Json -Compress
"""
    path = tmp_path / "concurrent.ps1"
    path.write_text(script)
    args = ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(path)]
    first = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    second = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    outputs = [p.communicate(timeout=15) for p in (first, second)]
    values = [json.loads(out) for out, err in outputs]
    assert sorted(v["state"] for v in values) == ["blocked", "observation_timeout"]
    assert (
        next(v for v in values if v["state"] == "blocked")["code"]
        == "START_LEASE_PRESENT"
    )
    again = subprocess.run(args, capture_output=True, text=True, timeout=15)
    assert json.loads(again.stdout)["code"] == "START_LEASE_PRESENT"
    assert marker.read_text().splitlines() == ["child"]
    # Let the fake finish normally; never terminate/kill a child in this test.
    import time

    time.sleep(4)
