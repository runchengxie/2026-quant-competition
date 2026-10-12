"""Exercise the real urllib request pipeline with an in-memory HTTPS provider."""

from collections import deque
from email.message import Message
from io import BytesIO
import json
from urllib.error import URLError
from urllib.request import HTTPSHandler
from urllib.response import addinfourl

import pytest


PRIMARY_KEY = "test-primary-key"
BACKUP_KEY = "test-backup-key"
PAYLOAD = {"token": "BTC", "period": "1h"}
RESULT = {"data": [{"token": "BTC", "value": 0.5}]}


class InMemoryProvider:
    """Replace only HTTPS I/O; keep request creation and HTTP error handling real."""

    def __init__(self):
        self.replies = deque()
        self.requests = []

    def respond(self, request):
        self.requests.append(request)
        if not self.replies:
            raise AssertionError("Unexpected additional provider request")
        reply = self.replies.popleft()
        if isinstance(reply, Exception):
            raise reply
        status, body, *location = reply
        headers = Message()
        headers["Content-Type"] = "application/json"
        if location:
            headers["Location"] = location[0]
        response = addinfourl(BytesIO(body), headers, request.full_url, status)
        response.msg = "provider response"
        return response


@pytest.fixture
def provider(monkeypatch):
    provider = InMemoryProvider()
    monkeypatch.setattr(HTTPSHandler, "https_open", provider.respond)
    return provider


def make_client(*, primary=PRIMARY_KEY, backup=BACKUP_KEY, timeout=15.0):
    from adapters.cryptoracle import CryptoracleClient

    return CryptoracleClient.from_environment(
        {
            "CRYPTORACLE_API_KEY": primary,
            "CRYPTORACLE_API_KEY_BACKUP": backup,
            "CRYPTORACLE_API_BASE_URL": "https://provider.example/api/",
        },
        timeout=timeout,
    )


def test_success_uses_primary_key_and_sends_json_with_timeout(provider):
    client = make_client(timeout=3.0)
    provider.replies.append((200, json.dumps(RESULT).encode()))

    assert client.post("/indicators", PAYLOAD) == RESULT

    (request,) = provider.requests
    assert request.full_url == "https://provider.example/api/indicators"
    assert request.get_method() == "POST"
    assert request.get_header("X-api-key") == PRIMARY_KEY
    assert request.get_header("Content-type") == "application/json"
    assert json.loads(request.data) == PAYLOAD
    assert request.timeout == 3.0


@pytest.mark.parametrize("status", [401, 403, 429])
def test_key_failure_retries_same_request_once_with_backup(provider, status):
    client = make_client()
    provider.replies.extend(
        [(status, b"rejected primary"), (200, json.dumps(RESULT).encode())]
    )

    assert client.post("/indicators", PAYLOAD) == RESULT

    assert [request.get_header("X-api-key") for request in provider.requests] == [
        PRIMARY_KEY,
        BACKUP_KEY,
    ]
    first, second = provider.requests
    assert first.data == second.data
    assert first.full_url == second.full_url
    assert first.timeout == second.timeout


@pytest.mark.parametrize(
    "backup", ["", "  ", PRIMARY_KEY, "replace-with-your-backup-access-key"]
)
def test_absent_placeholder_or_duplicate_backup_does_not_retry(provider, backup):
    client = make_client(backup=backup)
    from adapters.cryptoracle import CryptoracleAPIError

    provider.replies.append((401, f"rejected {PRIMARY_KEY}".encode()))

    with pytest.raises(CryptoracleAPIError) as failure:
        client.post("/indicators", PAYLOAD)

    assert failure.value.status_code == 401
    assert len(provider.requests) == 1
    assert PRIMARY_KEY not in str(failure.value)
    assert PRIMARY_KEY not in repr(failure.value)


@pytest.mark.parametrize("primary", ["", " ", "replace-with-your-access-key"])
def test_backup_can_be_used_when_primary_is_unset(provider, primary):
    client = make_client(primary=primary)
    provider.replies.append((200, json.dumps(RESULT).encode()))

    assert client.post("/indicators", PAYLOAD) == RESULT
    assert provider.requests[0].get_header("X-api-key") == BACKUP_KEY
    assert len(provider.requests) == 1


def test_exhausted_keys_report_final_status_without_secret_response(provider):
    client = make_client()
    from adapters.cryptoracle import CryptoracleAPIError

    provider.replies.extend([(401, PRIMARY_KEY.encode()), (429, BACKUP_KEY.encode())])

    with pytest.raises(CryptoracleAPIError) as failure:
        client.post("/indicators", PAYLOAD)

    assert failure.value.status_code == 429
    assert len(provider.requests) == 2
    assert PRIMARY_KEY not in str(failure.value)
    assert BACKUP_KEY not in str(failure.value)


def test_http_200_invalid_key_business_code_retries_with_backup(provider):
    client = make_client()
    success = {"code": 200, "msg": "success", "data": RESULT}
    provider.replies.extend(
        [
            (200, json.dumps({"code": 202, "msg": "APIKEY \u65e0\u6548"}).encode()),
            (200, json.dumps(success).encode()),
        ]
    )

    assert client.post("/v2.1/coin/list", {"timeType": "1h"}) == success
    assert [request.get_header("X-api-key") for request in provider.requests] == [
        PRIMARY_KEY,
        BACKUP_KEY,
    ]
    assert provider.requests[0].data == provider.requests[1].data


@pytest.mark.parametrize("backup", ["", PRIMARY_KEY])
def test_business_auth_failure_without_distinct_backup_raises_safe_error(
    provider, backup
):
    client = make_client(backup=backup)
    from adapters.cryptoracle import CryptoracleAPIError

    provider.replies.append(
        (200, json.dumps({"code": 202, "msg": PRIMARY_KEY}).encode())
    )

    with pytest.raises(CryptoracleAPIError) as failure:
        client.post("/v2.1/coin/list", {})

    assert failure.value.status_code == 200
    assert failure.value.business_code == 202
    assert PRIMARY_KEY not in str(failure.value)
    assert len(provider.requests) == 1


def test_both_keys_rejected_with_business_code_do_not_retry_again(provider):
    client = make_client()
    from adapters.cryptoracle import CryptoracleAPIError

    provider.replies.extend(
        [
            (200, json.dumps({"code": 202, "msg": PRIMARY_KEY}).encode()),
            (200, json.dumps({"code": 202, "msg": BACKUP_KEY}).encode()),
        ]
    )

    with pytest.raises(CryptoracleAPIError) as failure:
        client.post("/v2.1/coin/list", {})

    assert failure.value.business_code == 202
    assert BACKUP_KEY not in str(failure.value)
    assert len(provider.requests) == 2


@pytest.mark.parametrize("code", [201, 400, 500])
def test_other_business_failures_are_reported_without_rotating_keys(provider, code):
    client = make_client()
    from adapters.cryptoracle import CryptoracleAPIError

    provider.replies.append((200, json.dumps({"code": code, "msg": "error"}).encode()))

    with pytest.raises(CryptoracleAPIError) as failure:
        client.post("/v2.1/coin/list", {})

    assert failure.value.status_code == 200
    assert failure.value.business_code == code
    assert len(provider.requests) == 1


@pytest.mark.parametrize("status", [400, 404, 500, 503])
def test_endpoint_or_server_errors_do_not_trigger_key_rotation(provider, status):
    client = make_client()
    from adapters.cryptoracle import CryptoracleAPIError

    provider.replies.append((status, b"provider error"))

    with pytest.raises(CryptoracleAPIError) as failure:
        client.post("/indicators", PAYLOAD)

    assert failure.value.status_code == status
    assert len(provider.requests) == 1


def test_redirect_is_not_followed_with_credentials(provider):
    client = make_client()
    from adapters.cryptoracle import CryptoracleAPIError

    provider.replies.append((302, b"redirect", "https://other.example/indicators"))

    with pytest.raises(CryptoracleAPIError) as failure:
        client.post("/indicators", PAYLOAD)

    assert failure.value.status_code == 302
    assert len(provider.requests) == 1


@pytest.mark.parametrize("body", [b"not JSON", b"\xff"])
def test_invalid_response_does_not_trigger_key_rotation(provider, body):
    client = make_client()
    from adapters.cryptoracle import CryptoracleAPIError

    provider.replies.append((200, body))

    with pytest.raises(CryptoracleAPIError, match="JSON"):
        client.post("/indicators", PAYLOAD)

    assert len(provider.requests) == 1


@pytest.mark.parametrize("error", [URLError(PRIMARY_KEY), TimeoutError(PRIMARY_KEY)])
def test_transport_failure_is_sanitized_and_does_not_rotate_keys(provider, error):
    client = make_client()
    from adapters.cryptoracle import CryptoracleAPIError

    provider.replies.append(error)

    with pytest.raises(CryptoracleAPIError) as failure:
        client.post("/indicators", PAYLOAD)

    assert failure.value.status_code is None
    assert PRIMARY_KEY not in str(failure.value)
    assert len(provider.requests) == 1


def test_each_new_request_prefers_primary_key(provider):
    client = make_client()
    provider.replies.extend(
        [
            (401, b"rejected"),
            (200, b'{"source": "backup"}'),
            (200, b'{"source": "primary"}'),
        ]
    )

    assert client.post("/indicators", PAYLOAD) == {"source": "backup"}
    assert client.post("/indicators", PAYLOAD) == {"source": "primary"}
    assert [request.get_header("X-api-key") for request in provider.requests] == [
        PRIMARY_KEY,
        BACKUP_KEY,
        PRIMARY_KEY,
    ]


def test_environment_settings_trim_keys_and_hide_them_in_repr(monkeypatch, provider):
    from adapters.cryptoracle import CryptoracleClient, CryptoracleSettings

    monkeypatch.setenv("CRYPTORACLE_API_KEY", f" {PRIMARY_KEY} ")
    monkeypatch.setenv("CRYPTORACLE_API_KEY_BACKUP", f" {BACKUP_KEY} ")
    monkeypatch.delenv("CRYPTORACLE_API_BASE_URL", raising=False)
    settings = CryptoracleSettings.from_environment()
    client = CryptoracleClient.from_environment()
    provider.replies.append((200, b"{}"))

    assert client.post("/indicators", {}) == {}
    assert (
        provider.requests[0].full_url
        == "https://service.cryptoracle.network/openapi/indicators"
    )
    assert provider.requests[0].get_header("X-api-key") == PRIMARY_KEY
    for representation in (repr(settings), repr(client)):
        assert PRIMARY_KEY not in representation
        assert BACKUP_KEY not in representation


def test_no_usable_key_raises_clear_configuration_error():
    from adapters.cryptoracle import CryptoracleConfigurationError, CryptoracleSettings

    with pytest.raises(CryptoracleConfigurationError, match="API_KEY"):
        CryptoracleSettings.from_environment(
            {"CRYPTORACLE_API_KEY": "replace-with-your-access-key"}
        )


def test_legacy_official_host_gets_documented_openapi_prefix(provider):
    from adapters.cryptoracle import CryptoracleClient

    client = CryptoracleClient.from_environment(
        {
            "CRYPTORACLE_API_BASE_URL": "https://service.cryptoracle.network/",
            "CRYPTORACLE_API_KEY_BACKUP": BACKUP_KEY,
        }
    )
    provider.replies.append((200, b'{"code": 200, "msg": "success", "data": {}}'))

    assert client.post("/v2.1/coin/list", {"timeType": "1h"})["code"] == 200
    assert (
        provider.requests[0].full_url
        == "https://service.cryptoracle.network/openapi/v2.1/coin/list"
    )


@pytest.mark.parametrize("field", ["api_key", "backup_api_key"])
@pytest.mark.parametrize(
    "invalid_key", ["test-key\nInjected: secret", "test-key\rsecret", "test-key\u200b"]
)
def test_invalid_header_values_are_rejected_without_exposing_keys(field, invalid_key):
    from adapters.cryptoracle import CryptoracleConfigurationError, CryptoracleSettings

    with pytest.raises(CryptoracleConfigurationError) as failure:
        CryptoracleSettings(**{field: invalid_key})

    assert invalid_key not in str(failure.value)


@pytest.mark.parametrize(
    "url",
    [
        "http://provider.example",
        "https://user:pass@provider.example",
        "https:///",
        "https://provider.example?query=1",
    ],
)
def test_invalid_base_url_is_rejected_before_sending_keys(provider, url):
    from adapters.cryptoracle import CryptoracleConfigurationError, CryptoracleSettings

    with pytest.raises(CryptoracleConfigurationError, match="BASE_URL"):
        CryptoracleSettings.from_environment(
            {"CRYPTORACLE_API_KEY": PRIMARY_KEY, "CRYPTORACLE_API_BASE_URL": url}
        )

    assert not provider.requests


@pytest.mark.parametrize(
    "path",
    [
        "https://other.example/indicators",
        "//other.example/indicators",
        "",
        "/indicators#fragment",
    ],
)
def test_endpoint_cannot_override_configured_host(provider, path):
    client = make_client()
    from adapters.cryptoracle import CryptoracleConfigurationError

    with pytest.raises(CryptoracleConfigurationError, match="endpoint"):
        client.post(path, PAYLOAD)

    assert not provider.requests


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), True])
def test_timeout_must_be_finite_and_positive(timeout):
    from adapters.cryptoracle import CryptoracleConfigurationError

    with pytest.raises(CryptoracleConfigurationError, match="timeout"):
        make_client(timeout=timeout)
