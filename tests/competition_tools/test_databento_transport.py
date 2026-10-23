import io
import os
import subprocess
import time
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


def test_absolute_deadline_interrupts_inflight_read(tmp_path):
    class Slow(Response):
        def read(self, size=-1):
            time.sleep(0.4)
            return b"1"

    t = transport(tmp_path, [])
    t.opener.open = lambda *args, **kwargs: Slow()
    t.started = time.monotonic() - 119.9
    started = time.monotonic()
    with pytest.raises(ValueError, match="TIME_BUDGET"):
        t.get_metadata("metadata.get_cost", {})
    assert time.monotonic() - started < 0.3


def test_junction_substitution_prevents_request(tmp_path):
    parent = tmp_path / "late"
    other = tmp_path / "other"
    other.mkdir()
    t = transport(tmp_path, [b"1"])
    t.ledger = parent / "requests.jsonl"
    if os.name == "nt":
        run = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(parent), str(other)], capture_output=True
        )
        assert run.returncode == 0
    else:
        parent.symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError, match="REPARSE"):
        t.get_metadata("metadata.get_cost", {})
    assert not t.opener.calls


def test_raw_csv_preserves_original_response_bytes(tmp_path):
    raw = b"\xef\xbb\xbfa,b\r\n1,2\r\n"
    t = transport(tmp_path, [raw])
    target = tmp_path / "raw.csv"
    t.download_csv({}, target)
    assert target.read_bytes() == raw


def test_error_body_read_obeys_absolute_deadline(tmp_path):
    class Slow(Response):
        def read(self, size=-1):
            time.sleep(0.4)
            return b"error"

    t = transport(
        tmp_path, [HTTPError("https://hist.databento.com", 500, "error", {}, Slow())]
    )
    t.started = time.monotonic() - 119.9
    started = time.monotonic()
    with pytest.raises(ValueError):
        t.get_metadata("metadata.get_cost", {})
    assert time.monotonic() - started < 0.3


def test_junction_substitution_during_response_prevents_raw_write(tmp_path):
    parent = tmp_path / "late"
    other = tmp_path / "other"
    other.mkdir()

    class Swap(Response):
        def read(self, size=-1):
            if not parent.exists():
                if os.name == "nt":
                    run = subprocess.run(
                        ["cmd", "/c", "mklink", "/J", str(parent), str(other)],
                        capture_output=True,
                    )
                    assert run.returncode == 0
                else:
                    parent.symlink_to(other, target_is_directory=True)
            return super().read(size)

    t = transport(tmp_path, [])
    t.opener.open = lambda *args, **kwargs: Swap(b"a,b\n1,2\n")
    with pytest.raises(ValueError, match="REPARSE"):
        t.download_csv({}, parent / "bars.csv")
    assert not (other / "bars.csv").exists()
