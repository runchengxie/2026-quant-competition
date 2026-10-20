"""Optional login preparation uses read-only probes and explicit activation."""

import json
from types import SimpleNamespace
import pytest

from competition_tools.team import gateway


class HistoricalClient:
    def __init__(self):
        self.disconnected = False

    def connect(self, host, port, **kwargs):
        assert (host, port) == ("127.0.0.1", 4002)
        assert kwargs["readonly"] is True

    def isConnected(self):
        return True

    def disconnect(self):
        self.disconnected = True


def connection(tmp_path):
    path = tmp_path / "connection.json"
    path.write_text(json.dumps({"host": "127.0.0.1", "port": 4002, "client_id": 1234}))
    return path


def test_probe_is_readonly_and_always_disconnects(tmp_path):
    client = HistoricalClient()
    result = gateway.probe_api(connection(tmp_path), client_factory=lambda: client)
    assert result["state"] == "ready"
    assert result["account_identity"] == "not_checked"
    assert result["historical_data"] == "not_checked"
    assert client.disconnected


def test_endpoint_json_rejects_password_instead_of_forwarding_it(tmp_path):
    path = connection(tmp_path)
    value = json.loads(path.read_text()) | {"password": "private-sentinel"}
    path.write_text(json.dumps(value))
    result = gateway.probe_api(path)
    assert result["state"] == "blocked"
    assert "private-sentinel" not in str(result)


def test_ready_api_needs_no_launcher_and_starts_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        gateway, "probe_api", lambda *a, **k: {"state": "ready", "code": "API_READY"}
    )
    monkeypatch.setattr(
        gateway.subprocess,
        "run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not launch")),
    )
    assert gateway.ensure_gateway(connection(tmp_path))["startup_attempted"] is False


def test_disabled_activation_never_launches(tmp_path, monkeypatch):
    monkeypatch.setattr(gateway.sys, "platform", "win32")
    monkeypatch.setattr(gateway, "probe_api", lambda *a, **k: {"state": "not_ready"})
    monkeypatch.setattr(
        gateway.gl,
        "build_launch_spec",
        lambda *a: {"status": {"activation_authorized": False}},
    )
    result = gateway.ensure_gateway(
        connection(tmp_path),
        launcher_config=tmp_path / "launcher.json",
        workspace=tmp_path / "workspace.toml",
        wrapper=tmp_path / "wrapper.ps1",
    )
    assert result["code"] == "ACTIVATION_NOT_AUTHORIZED"
    assert result["startup_attempted"] is False


@pytest.mark.parametrize(
    "output,expected,probe_count",
    [
        ('{"state":"api_ready","api":"connected"}', "ready", 2),
        ("[]", "blocked", 1),
        ('{"state":"blocked","code":"private token sentinel"}', "blocked", 1),
    ],
)
def test_one_explicit_wrapper_call_contains_no_credentials(
    tmp_path, monkeypatch, output, expected, probe_count
):
    monkeypatch.setattr(gateway.sys, "platform", "win32")
    probes = []

    def probe(*args, **kwargs):
        probes.append(True)
        return {"state": "not_ready" if len(probes) == 1 else "ready"}

    monkeypatch.setattr(gateway, "probe_api", probe)
    monkeypatch.setattr(
        gateway.gl,
        "build_launch_spec",
        lambda *a: {
            "status": {"activation_authorized": True},
            "launcher_ready": True,
            "start_supported": True,
        },
    )
    monkeypatch.setattr(gateway.gl, "owner_only_acl", lambda p: True)
    wrapper = tmp_path / "Start-PaperGateway.ps1"
    wrapper.write_text("# external deployed wrapper")
    wrapper.with_name("PaperGateway.psm1").write_text("# external module")
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert kwargs["timeout"] == 330
        assert "password" not in " ".join(argv).lower()
        return SimpleNamespace(returncode=0, stdout=output)

    monkeypatch.setattr(gateway.subprocess, "run", run)
    result = gateway.ensure_gateway(
        connection(tmp_path),
        launcher_config=tmp_path / "launcher.json",
        workspace=tmp_path / "workspace.toml",
        wrapper=wrapper,
    )
    assert result["state"] == expected and result["startup_attempted"] is True
    assert "private token sentinel" not in str(result)
    assert len(calls) == 1
    assert calls[0][calls[0].index("-Action") + 1] == "ensure"
    assert len(probes) == probe_count


def test_disconnect_failure_is_blocked_without_private_exception(tmp_path):
    class FailingDisconnect(HistoricalClient):
        def disconnect(self):
            raise RuntimeError("private-session-sentinel")

    result = gateway.probe_api(connection(tmp_path), client_factory=FailingDisconnect)
    assert result["state"] == "blocked"
    assert "private-session-sentinel" not in str(result)


def test_cli_help_exposes_explicit_opt_in(capsys):
    import pytest
    from competition_tools.team.__main__ import main

    with pytest.raises(SystemExit) as exc:
        main(["data", "--help"])
    assert exc.value.code == 0
    assert "--ensure-gateway" in capsys.readouterr().out


def test_blocked_gateway_prevents_provider_acquisition(tmp_path, monkeypatch):
    from competition_tools.team.config import TeamConfig
    from competition_tools.team.data import execute
    from competition_tools.datasets import acquisition

    spec = {
        "schema": "competition.dataset_spec.v1",
        "dataset_id": "pilot",
        "version": "v1",
        "source": "ibkr",
        "market": "US",
        "products": ["SPY"],
        "quote_currency": "USD",
        "start": "2024-01-01",
        "end": "2024-01-31",
        "timezone": "America/New_York",
        "calendar": "XNYS",
        "price_basis": "split_adjusted",
        "universe_status": "fixed_current",
        "budget": {"requests": 100, "bytes": 100000, "seconds": 1800},
        "credential_file": str(connection(tmp_path)),
        "contracts": [
            {"product": "SPY", "con_id": 123, "exchange": "SMART", "currency": "USD"}
        ],
    }
    file = tmp_path / "spec.json"
    file.write_text(json.dumps(spec))
    monkeypatch.setattr(
        gateway,
        "ensure_gateway",
        lambda *a, **k: {"state": "blocked", "code": "ACTIVATION_NOT_AUTHORIZED"},
    )
    monkeypatch.setattr(
        acquisition,
        "acquire",
        lambda *a: (_ for _ in ()).throw(AssertionError("provider must not run")),
    )
    value = execute(
        "acquire", TeamConfig(tmp_path, tmp_path / "envs"), file, ensure_gateway=True
    )
    assert value["issue_codes"] == ["ACTIVATION_NOT_AUTHORIZED"]
    assert not (tmp_path / "2026-quant-competition/datasets/pilot/v1.partial").exists()
