"""Acceptance distinguishes account, contract and history evidence."""

import json
import subprocess
from types import SimpleNamespace

import pytest

from competition_tools.team.gateway_verification import verify_reading


@pytest.fixture(autouse=True)
def stock_factory(monkeypatch):
    monkeypatch.setattr(
        "competition_tools.team.gateway_verification._stock",
        lambda spec: SimpleNamespace(
            symbol=spec["symbol"],
            exchange=spec["exchange"],
            currency=spec["currency"],
            secType="STK",
            conId=0,
        ),
    )


@pytest.fixture
def endpoint(tmp_path):
    path = tmp_path / "endpoint.json"
    path.write_text(json.dumps({"host": "127.0.0.1", "port": 4002, "client_id": 741}))
    return path


@pytest.fixture
def contract():
    return {
        "product": "SPY",
        "symbol": "SPY",
        "exchange": "SMART",
        "currency": "USD",
        "role": "benchmark",
    }


class Client:
    def __init__(self, failure=None):
        self.failure = failure
        self.disconnected = False
        self.history_calls = 0

    def connect(self, host, port, **kwargs):
        assert kwargs["readonly"] is True
        if self.failure == "connect":
            raise ConnectionError("PRIVATE_SENTINEL")

    def isConnected(self):
        return True

    def managedAccounts(self):
        return [
            "U_PRIVATE_SENTINEL" if self.failure == "account" else "DU_PRIVATE_SENTINEL"
        ]

    def qualifyContracts(self, contract):
        assert self.RequestTimeout == 8
        if self.failure == "qualify":
            raise RuntimeError("PRIVATE_SENTINEL")
        contract.conId = 42
        if self.failure == "mismatch":
            contract.currency = "EUR"
        return [contract]

    def reqHistoricalData(self, contract, **kwargs):
        self.history_calls += 1
        assert kwargs["durationStr"] == "5 D"
        assert kwargs["barSizeSetting"] == "1 day"
        assert kwargs["useRTH"] is True
        assert kwargs["timeout"] == 8
        if self.failure == "history":
            raise RuntimeError("PRIVATE_SENTINEL")
        if self.failure == "empty":
            return []
        return [SimpleNamespace(close=float("nan") if self.failure == "nan" else 100)]

    def disconnect(self):
        self.disconnected = True


def test_default_does_not_certify_history_or_server(endpoint, contract):
    client = Client()
    report = verify_reading(endpoint, [contract], client_factory=lambda: client)
    assert report["api"] == "connected"
    assert report["account_prefix"] == "paper_single"
    assert report["contract"] == "matched"
    assert report["historical"] == "not_checked"
    assert report["server_read_only"] == "not_verified"
    assert report["intended_read_only"] == "not_verified"
    assert report["issue_codes"] == []
    assert client.history_calls == 0
    assert client.disconnected
    assert "PRIVATE_SENTINEL" not in json.dumps(report)


def test_explicit_history_records_only_availability(endpoint, contract):
    report = verify_reading(
        endpoint, [contract], historical=True, client_factory=Client
    )
    assert report["historical"] == "available"
    assert report["server_read_only"] == "not_verified"


def test_failed_history_preserves_separate_qualified_contract_evidence(
    endpoint, contract
):
    report = verify_reading(
        endpoint, [contract], historical=True, client_factory=lambda: Client("history")
    )
    assert report["contract"] == "matched"
    assert report["historical"] == "blocked"


def test_ini_reparse_path_is_blocked_without_reading(
    endpoint, contract, tmp_path, monkeypatch
):
    from competition_tools import gateway_launcher as gl

    def reparse(*args, **kwargs):
        raise gl.LauncherError("REPARSE_PATH")

    monkeypatch.setattr(gl, "_path", reparse)
    report = verify_reading(
        endpoint, [contract], ini_path=tmp_path / "private.ini", client_factory=Client
    )
    assert report["issue_codes"] == ["REPARSE_PATH"]
    assert report["api"] == "not_checked"


@pytest.mark.parametrize(
    "failure,field,code",
    [
        ("account", "account_prefix", "PAPER_ACCOUNT_REQUIRED"),
        ("mismatch", "contract", "CONTRACT_MISMATCH"),
        ("qualify", "contract", "CONTRACT_READ_FAILED"),
        ("history", "historical", "HISTORICAL_READ_FAILED"),
        ("empty", "historical", "HISTORICAL_UNAVAILABLE"),
        ("nan", "historical", "HISTORICAL_UNAVAILABLE"),
    ],
)
def test_failed_evidence_is_blocked_without_private_errors(
    endpoint, contract, failure, field, code
):
    client = Client(failure)
    report = verify_reading(
        endpoint, [contract], historical=True, client_factory=lambda: client
    )
    assert report[field] == "blocked"
    assert code in report["issue_codes"]
    assert "PRIVATE_SENTINEL" not in json.dumps(report)
    assert client.disconnected


def test_invalid_contracts_do_not_connect(endpoint, contract):
    def forbidden():
        pytest.fail("Invalid contract must be rejected before connection")

    report = verify_reading(
        endpoint,
        [contract | {"password": "PRIVATE_SENTINEL"}],
        client_factory=forbidden,
    )
    assert report["issue_codes"] == ["INVALID_CONTRACT_SPEC"]
    assert report["api"] == "not_checked"


@pytest.mark.parametrize("mode,intent", [("yes", "enabled"), ("no", "disabled")])
def test_ini_intent_is_not_runtime_evidence(
    endpoint, contract, tmp_path, monkeypatch, mode, intent
):
    from competition_tools import gateway_launcher as gl

    ini = tmp_path / "ibc.ini"
    ini.write_text(
        "TradingMode=paper\nReadOnlyApi=yes\nReadOnlyLogin=no\nExistingSessionDetectedAction=manual\nReloginAfterSecondFactorAuthenticationTimeout=no\nFIX=no\nIbPassword=PRIVATE_SENTINEL\nSecondFactorAuthenticationExitInterval=60\nCommandServerPort=0\n"
    )
    monkeypatch.setattr(gl, "owner_only_acl", lambda path: True)
    ini.write_text(ini.read_text().replace("ReadOnlyApi=yes", f"ReadOnlyApi={mode}"))
    report = verify_reading(endpoint, [contract], ini_path=ini, client_factory=Client)
    assert report["intended_read_only"] == intent
    assert report["server_read_only"] == "not_verified"
    assert "PRIVATE_SENTINEL" not in json.dumps(report)
    ini.write_text(ini.read_text() + "Unknown=PRIVATE_SENTINEL\n")
    report = verify_reading(endpoint, [contract], ini_path=ini, client_factory=Client)
    assert report["intended_read_only"] == "blocked"
    assert "UNSAFE_IBC_CONFIGURATION" in report["issue_codes"]


def test_unsafe_ini_acl_blocks_before_connect(
    endpoint, contract, tmp_path, monkeypatch
):
    from competition_tools import gateway_launcher as gl

    ini = tmp_path / "ibc.ini"
    ini.write_text("IbPassword=PRIVATE_SENTINEL")
    monkeypatch.setattr(gl, "owner_only_acl", lambda path: False)
    report = verify_reading(endpoint, [contract], ini_path=ini, client_factory=Client)
    assert report["issue_codes"] == ["UNSAFE_ACL"]
    assert report["api"] == "not_checked"


def test_cli_help_needs_no_config_or_sdk(capsys):
    from competition_tools.team.__main__ import main

    with pytest.raises(SystemExit) as error:
        main(["gateway", "verify", "--help"])
    assert error.value.code == 0
    assert "--historical" in capsys.readouterr().out


def test_acl_probe_timeout_returns_redacted_report_without_connection(
    endpoint, contract, tmp_path, monkeypatch, capsys
):
    from competition_tools import gateway_launcher as gl
    from competition_tools.team.__main__ import main

    ini = tmp_path / "ibc.ini"
    ini.write_text("IbPassword=PRIVATE_SENTINEL")
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "schema": "competition.paper_contract_spec.v1",
                "market": "US",
                "contracts": [contract],
            }
        )
    )

    def timeout(path):
        raise subprocess.TimeoutExpired("PRIVATE_SENTINEL", 20)

    monkeypatch.setattr(gl, "owner_only_acl", timeout)
    assert (
        main(
            [
                "gateway",
                "verify",
                "--connection-file",
                str(endpoint),
                "--contract-spec",
                str(spec),
                "--ini-file",
                str(ini),
            ]
        )
        == 2
    )
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["api"] == "not_checked"
    assert report["issue_codes"] == ["IBC_CONFIGURATION_CHECK_FAILED"]
    assert "PRIVATE_SENTINEL" not in output
