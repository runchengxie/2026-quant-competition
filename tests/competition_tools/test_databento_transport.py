import io
from decimal import Decimal
from urllib.error import HTTPError

import pytest

from competition_tools.datasets.databento_transport import (
    DatabentoTransport,
    validate_cost_bound,
)


class Response(io.BytesIO):
    status = 200
    headers = {}


class Opener:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append(request)
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return Response(value)


def transport(tmp_path, values, **kwargs):
    key = tmp_path / "key.env"
    key.write_text("DATABENTO_API_KEY=synthetic-secret\n")
    return DatabentoTransport(
        key,
        {
            "metadata_requests": 5,
            "download_requests": 1,
            "bytes": 20971520,
            "seconds": 120,
            "max_cost_usd": "0.10",
        },
        tmp_path / "requests.jsonl",
        opener=Opener(values),
        **kwargs,
    )


def test_transport_does_not_follow_redirect_or_echo_secret(tmp_path):
    t = transport(
        tmp_path,
        [
            HTTPError(
                "https://hist.databento.com",
                302,
                "synthetic-secret",
                {},
                io.BytesIO(b"synthetic-secret"),
            )
        ],
    )
    with pytest.raises(ValueError, match="PROVIDER_HTTP_302"):
        t.get_metadata("metadata.get_cost", {})
    assert "synthetic-secret" not in t.ledger.read_text()
    assert len(t.opener.calls) == 1
    with pytest.raises(ValueError, match="ENDPOINT"):
        t.get_metadata("https://evil.test", {})


def test_budget_counts_failed_requests(tmp_path):
    t = transport(tmp_path, [b"not json"] * 5)
    for _ in range(5):
        with pytest.raises(ValueError):
            t.get_metadata("metadata.get_cost", {})
    with pytest.raises(ValueError, match="REQUEST_BUDGET"):
        t.get_metadata("metadata.get_cost", {})
    assert t.spent()["metadata_requests"] == 5
    assert t.spent()["bytes"] == 40


def test_cost_bound_requires_units_and_full_request():
    evidence = {
        "unit_price_usd_per_gb": "20",
        "billable_bytes": 150000,
        "record_count": 2500,
        "request_sha256": "a" * 64,
        "quote_request_sha256": "a" * 64,
    }
    result = validate_cost_bound("0.004", evidence, Decimal("0.10"))
    assert Decimal(result["conservative_cost_usd"]) <= Decimal("0.10")
    for bad in ("NaN", "-1", "0.11"):
        with pytest.raises(ValueError):
            validate_cost_bound(bad, evidence, Decimal("0.10"))
    for changes in (
        {"record_count": 4000},
        {"unit_price_usd_per_gb": "10000"},
        {"quote_request_sha256": "b" * 64},
        {"billable_bytes": True},
    ):
        with pytest.raises(ValueError):
            validate_cost_bound("0.004", {**evidence, **changes}, Decimal("0.10"))


def test_error_body_read_failure_is_sanitized(tmp_path):
    t = transport(tmp_path, [RuntimeError("synthetic-secret")])
    with pytest.raises(ValueError, match="PROVIDER_CONNECTION_FAILED"):
        t.get_metadata("metadata.get_cost", {})
    assert "synthetic-secret" not in t.ledger.read_text()


def test_secret_echo_and_nonfinite_json_rejected(tmp_path):
    t = transport(tmp_path, [b'{"x":"synthetic-secret"}', b"NaN"])
    for _ in range(2):
        with pytest.raises(ValueError):
            t.get_metadata("metadata.get_cost", {})
    assert "synthetic-secret" not in t.ledger.read_text()


def test_elapsed_time_starts_at_transport_creation(tmp_path):
    clock = [0.0]
    t = transport(tmp_path, [b"1"], monotonic=lambda: clock[0])
    clock[0] = 121
    with pytest.raises(ValueError, match="TIME_BUDGET"):
        t.get_metadata("metadata.get_cost", {})
    assert not t.opener.calls
