import io
import json
from urllib.error import HTTPError, URLError

import pytest

from competition_tools.datasets.dex_transport import DexTransport
from competition_tools.datasets.dex_spec import CAPS


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Response(io.BytesIO):
    headers = {"Content-Type": "application/json"}


def make(tmp_path, handler, **budget):
    key = tmp_path / "credential.env"
    key.write_text("DEXPAPRIKA_API_KEY=fixture-only\n")
    clock = Clock()
    transport = DexTransport(
        CAPS | budget,
        key,
        tmp_path / "requests.jsonl",
        opener=handler,
        clock=clock,
        sleep=clock.sleep,
    )
    return transport, clock


@pytest.mark.parametrize(
    "endpoint", ["https://other.invalid/usage", "../usage", "search"]
)
def test_endpoint_rejected_before_credentials_or_ledger(tmp_path, endpoint):
    transport = DexTransport(CAPS, tmp_path / "absent", tmp_path / "ledger")
    with pytest.raises(ValueError, match="ENDPOINT_NOT_ALLOWED"):
        transport.get_json(endpoint)
    assert not transport.ledger.exists()


def test_headers_and_spacing(tmp_path):
    calls = []

    def handler(request, timeout):
        calls.append((request, timeout, clock.now))
        return Response(b"{}")

    transport, clock = make(tmp_path, handler)
    transport.get_json("usage")
    transport.get_json("networks")
    assert [c[2] for c in calls] == [0, 3]
    assert calls[0][0].full_url == "https://api-pro.dexpaprika.com/usage"
    assert calls[0][0].get_header("Authorization") == "fixture-only"
    assert calls[0][0].get_header("Accept-encoding") == "identity"
    assert calls[0][1] == 30
    assert "fixture-only" not in transport.ledger.read_text()


@pytest.mark.parametrize(
    "code,attempts", [(301, 1), (401, 1), (403, 1), (404, 1), (429, 2), (503, 2)]
)
def test_failed_bytes_charged_and_errors_sanitized(tmp_path, code, attempts):
    def handler(request, timeout):
        raise HTTPError(
            request.full_url,
            code,
            "fixture-only",
            {"Retry-After": "999"},
            io.BytesIO(b"fixture-only"),
        )

    transport, clock = make(tmp_path, handler)
    with pytest.raises(ValueError) as error:
        transport.get_json("usage")
    assert "fixture-only" not in str(error.value)
    assert transport.requests == attempts
    assert transport.bytes == attempts * len(b"fixture-only")
    assert clock.now <= 60
    assert "fixture-only" not in transport.ledger.read_text()


@pytest.mark.parametrize(
    "body",
    [
        b'{"echo":"fixture-only"}',
        b'{"echo":"fixture\\u002donly"}',
        b"<html>fixture-only</html>",
        b"NaN",
        b"1",
    ],
)
def test_untrusted_body_not_returned_or_retained(tmp_path, body):
    transport, _ = make(tmp_path, lambda *a, **k: Response(body))
    with pytest.raises(ValueError):
        transport.get_json("usage")
    assert "fixture-only" not in transport.ledger.read_text()


def test_network_exception_sanitized_and_bounded(tmp_path):
    def handler(*args, **kwargs):
        raise URLError("fixture-only")

    transport, _ = make(tmp_path, handler)
    with pytest.raises(ValueError, match="RETRIES_EXHAUSTED"):
        transport.get_json("usage")
    assert transport.requests == 2
    assert "fixture-only" not in transport.ledger.read_text()


def test_attempt_budget_includes_retries(tmp_path):
    def handler(*args, **kwargs):
        raise URLError("private")

    transport, _ = make(tmp_path, handler, requests=1)
    with pytest.raises(ValueError, match="REQUEST_BUDGET"):
        transport.get_json("usage")
    assert transport.requests == 1


def test_full_request_cap(tmp_path):
    transport, _ = make(tmp_path, lambda *a, **k: Response(b"{}"))
    for _ in range(100):
        transport.get_json("usage")
    with pytest.raises(ValueError, match="REQUEST_BUDGET"):
        transport.get_json("usage")
    assert transport.requests == 100


def test_byte_cap(tmp_path):
    transport, _ = make(tmp_path, lambda *a, **k: Response(b" " * 11), bytes=10)
    with pytest.raises(ValueError, match="BYTE_BUDGET"):
        transport.get_json("usage")
    assert transport.bytes == 11


def test_deadline_bounds_timeout_and_next_start(tmp_path):
    timeouts = []

    def handler(request, timeout):
        timeouts.append(timeout)
        return Response(b"{}")

    transport, clock = make(tmp_path, handler, seconds=4)
    clock.now = 2
    transport.get_json("usage")
    assert timeouts == [2]
    with pytest.raises(ValueError, match="TIME_BUDGET"):
        transport.get_json("usage")
    assert transport.requests == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"network": "../ethereum", "address": "0x" + "a" * 40},
        {
            "network": "ethereum",
            "address": "0x" + "a" * 40,
            "query": {"redirect": "https://other"},
        },
        {
            "network": "ethereum",
            "address": "0x" + "a" * 40,
            "query": {"interval": "1d"},
        },
    ],
)
def test_invalid_resource_before_network(tmp_path, kwargs):
    transport, _ = make(tmp_path, lambda *a, **k: pytest.fail("network called"))
    with pytest.raises(ValueError):
        transport.get_json("token_ohlcv", **kwargs)
    assert transport.requests == 0


def test_existing_ledger_never_resets_spent_budget(tmp_path):
    ledger = tmp_path / "requests.jsonl"
    ledger.write_text(json.dumps({"attempt": 1}) + "\n")
    with pytest.raises(ValueError, match="LEDGER_EXISTS"):
        DexTransport(CAPS, tmp_path / "key", ledger)


def test_failed_error_body_read_cannot_expose_exception_details(tmp_path):
    class Broken(io.BytesIO):
        def read(self, size=-1):
            raise OSError("fixture-only")

    def handler(request, timeout):
        raise HTTPError(request.full_url, 403, "private", {}, Broken())

    transport, _ = make(tmp_path, handler)
    with pytest.raises(ValueError, match="HTTP_403"):
        transport.get_json("usage")
    assert transport.requests == 1
