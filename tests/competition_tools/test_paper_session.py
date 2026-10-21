"""Guard access to broker data before exposing a connected client."""

import json
import logging

import pytest

from competition_tools.team.gateway import load_paper_endpoint
from competition_tools.team.paper_session import PaperReadError, PaperReadSession


@pytest.fixture
def endpoint(tmp_path):
    path = tmp_path / "connection.json"
    path.write_text(json.dumps({"host": "127.0.0.1", "port": 4002, "client_id": 741}))
    return path


class Client:
    def __init__(self, accounts=None, failure=None):
        self.accounts = ["DU_PRIVATE_SENTINEL"] if accounts is None else accounts
        self.failure = failure
        self.disconnected = False

    def connect(self, host, port, *, clientId, timeout, readonly):
        assert (host, port, clientId) == ("127.0.0.1", 4002, 741)
        assert readonly is True
        assert timeout == 8
        if self.failure == "connect":
            raise RuntimeError("PRIVATE_SENTINEL")

    def isConnected(self):
        return self.failure != "not_connected"

    def managedAccounts(self):
        return self.accounts

    def disconnect(self):
        self.disconnected = True
        if self.failure == "disconnect":
            raise RuntimeError("PRIVATE_SENTINEL")


def test_endpoint_rejects_password(endpoint):
    value = json.loads(endpoint.read_text()) | {"password": "PRIVATE_SENTINEL"}
    endpoint.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="^INVALID_PAPER_CONNECTION$"):
        load_paper_endpoint(endpoint)


@pytest.mark.parametrize("value", [True, 0, -1, 2**31, "741"])
def test_endpoint_rejects_invalid_client_id(endpoint, value):
    data = json.loads(endpoint.read_text()) | {"client_id": value}
    endpoint.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="INVALID_PAPER_CONNECTION"):
        load_paper_endpoint(endpoint)


def test_guarded_session_returns_client_and_restores_logging(endpoint):
    client = Client()
    logger = logging.getLogger("ib_insync")
    previous = logger.level
    session = PaperReadSession(endpoint, client_factory=lambda: client)
    with session as connected:
        assert connected is client
        assert session.account_check == {"status": "paper_single", "count": 1}
        assert "PRIVATE_SENTINEL" not in str(session.account_check)
    assert client.disconnected
    assert logger.level == previous


@pytest.mark.parametrize(
    "accounts",
    [[], ["U_PRIVATE_SENTINEL"], ["DU1", "DU2"], ["DU1", "U2"], ["DU"], "DU123"],
)
def test_non_single_paper_account_is_blocked_and_disconnected(endpoint, accounts):
    client = Client(accounts)
    with pytest.raises(PaperReadError, match="^PAPER_ACCOUNT_REQUIRED$"):
        with PaperReadSession(endpoint, client_factory=lambda: client):
            pytest.fail("Unverified client escaped the account guard")
    assert client.disconnected


@pytest.mark.parametrize(
    "failure,code",
    [
        ("connect", "API_READ_FAILED"),
        ("not_connected", "GATEWAY_API_NOT_READY"),
        ("disconnect", "API_DISCONNECT_FAILED"),
    ],
)
def test_sdk_failures_are_redacted_and_cleanup_restores_logging(
    endpoint, failure, code
):
    client = Client(failure=failure)
    logger = logging.getLogger("ib_insync")
    previous = logger.level
    with pytest.raises(PaperReadError, match=f"^{code}$"):
        with PaperReadSession(endpoint, client_factory=lambda: client):
            pass
    assert client.disconnected
    assert logger.level == previous


def test_body_exception_is_preserved_after_cleanup(endpoint):
    client = Client()
    with pytest.raises(ValueError, match="consumer failure"):
        with PaperReadSession(endpoint, client_factory=lambda: client):
            raise ValueError("consumer failure")
    assert client.disconnected
