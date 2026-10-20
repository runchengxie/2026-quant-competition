"""Network failures and caps must leave no falsely completed bytes."""

import io
from urllib.error import HTTPError

import pytest

from competition_tools.datasets.transport import Transport, DatasetBlocked

URL = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2024-01.zip"


def test_bad_host_rejected_before_network(tmp_path):
    client = Transport(
        {"requests": 20, "bytes": 1000, "seconds": 10}, tmp_path / "ledger.jsonl"
    )
    with pytest.raises(ValueError):
        client.fetch("https://evil.invalid/secret", tmp_path / "output")
    assert client.requests == 0


def test_retry_charges_budget_and_removes_partial_file(tmp_path):
    calls = []

    def opening(request, timeout):
        calls.append(request.full_url)
        raise HTTPError(request.full_url, 429, "limited", {"Retry-After": "0"}, None)

    client = Transport(
        {"requests": 2, "bytes": 1000, "seconds": 10},
        tmp_path / "ledger.jsonl",
        opener=opening,
    )
    with pytest.raises(DatasetBlocked, match="REQUEST_BUDGET"):
        client.fetch(URL, tmp_path / "output")
    assert len(calls) == 2
    assert not (tmp_path / "output").exists()


def test_byte_cap_rejects_body(tmp_path):
    client = Transport(
        {"requests": 2, "bytes": 3, "seconds": 10},
        tmp_path / "ledger.jsonl",
        opener=lambda r, timeout: io.BytesIO(b"12345"),
    )
    with pytest.raises(DatasetBlocked, match="BYTE_BUDGET"):
        client.fetch(URL, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_existing_file_never_overwritten(tmp_path):
    target = tmp_path / "output"
    target.write_bytes(b"retained")
    client = Transport(
        {"requests": 2, "bytes": 100, "seconds": 10}, tmp_path / "ledger.jsonl"
    )
    with pytest.raises(FileExistsError):
        client.fetch(URL, target)
    assert target.read_bytes() == b"retained"
