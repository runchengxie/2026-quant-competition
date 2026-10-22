import json

import pytest

from competition_tools.datasets.dex_acquisition import acquire_dex
from competition_tools.datasets.dex_storage import (
    publish_dex,
    inspect_dex,
    verify_dex_manifest,
)
from competition_tools.datasets.storage import digest
from competition_tools.datasets.dex_transport import DexTransport
from competition_tools.datasets.dex_spec import CAPS, dataset_identity, utc_hour
from test_dex_spec import sample
from test_dex_transport import Clock, Response
from test_dex_quality import candle


def case(tmp_path, *, missing=False, substitution=False, changed_overlap=False):
    spec = sample(tmp_path)
    protocol = {"dataset": dataset_identity(spec)}
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(protocol))
    spec["protocol_file"] = str(path)
    spec["protocol_sha256"] = digest(path)
    key = tmp_path / "key.env"
    key.write_text("DEXPAPRIKA_API_KEY=fixture-only\n")
    spec["credential_file"] = str(key)
    calls = []
    clock = Clock()

    def handler(request, timeout):
        from urllib.parse import urlsplit, parse_qs

        parsed = urlsplit(request.full_url)
        calls.append(request.full_url)
        if parsed.path == "/usage":
            value = {
                "plan": "pro",
                "requests_used": len(calls),
                "requests_left": 5000000 - len(calls),
                "period_started_at": "2026-10-01T00:00:00Z",
                "period_ends_at": "2026-11-01T00:00:00Z",
            }
        elif parsed.path == "/networks":
            value = [{"id": "solana"}]
        elif parsed.path.endswith("/ohlcv"):
            query = parse_qs(parsed.query)
            first = int(
                (utc_hour(query["start"][0]) - utc_hour(spec["start"])).total_seconds()
                / 3600
            )
            value = [candle(i) for i in range(first, first + 721)]
            if missing:
                value = value[1:]
            if changed_overlap and first > 0:
                value[0]["volume"] += 1
        else:
            value = {"id": "wrong" if substitution else spec["assets"][0]["address"]}
        return Response(json.dumps(value).encode())

    staging = tmp_path / "staging"
    transport = DexTransport(
        CAPS,
        key,
        staging / "requests-1.jsonl",
        opener=handler,
        clock=clock,
        sleep=clock.sleep,
    )
    return spec, staging, transport, calls


def test_three_chunks_and_independent_raw_reconstruction(tmp_path):
    spec, staging, transport, calls = case(tmp_path)
    receipt = acquire_dex(spec, staging, transport=transport)
    assert receipt["status"] == "completed"
    assert receipt["coverage"][0]["observed_intervals"] == 2160
    assert len([url for url in calls if "/ohlcv?" in url]) == 3
    destination = tmp_path / "published"
    manifest = publish_dex(staging, destination)
    assert manifest["availability"] == "bar_close_proxy_unverified"
    assert inspect_dex(destination / "manifest.json")["status"] == "completed"
    assert verify_dex_manifest(destination / "manifest.json")["spec_sha256"]
    normalized = json.loads((destination / "normalized/wrapped-sol.json").read_text())
    raw = json.loads((destination / "raw/wrapped-sol-0.json").read_text())
    assert normalized[0]["close"] == raw[0]["close"]
    assert len(normalized) == 2160
    with pytest.raises(FileExistsError):
        publish_dex(destination, destination)


@pytest.mark.parametrize(
    "option,reason",
    [
        ("substitution", "TOKEN_IDENTITY_MISMATCH"),
        ("changed_overlap", "CHANGED_OVERLAP"),
    ],
)
def test_bad_provider_identity_or_overlap_blocks(tmp_path, option, reason):
    spec, staging, transport, _ = case(tmp_path, **{option: True})
    receipt = acquire_dex(spec, staging, transport=transport)
    assert receipt["status"] == "blocked"
    assert reason in receipt["issues"]


def test_missing_hours_stay_partial(tmp_path):
    spec, staging, transport, _ = case(tmp_path, missing=True)
    receipt = acquire_dex(spec, staging, transport=transport)
    assert receipt["status"] == "partial"
    assert receipt["coverage"][0]["missing_intervals"] > 0


def test_unowned_and_changed_protocol_rejected_before_request(tmp_path):
    spec, staging, transport, _ = case(tmp_path)
    staging.mkdir()
    with pytest.raises(ValueError, match="UNOWNED_STAGING"):
        acquire_dex(spec, staging, transport=transport)
    assert transport.requests == 0


def test_protocol_hash_rejected_before_request(tmp_path):
    spec, staging, transport, _ = case(tmp_path)
    spec["protocol_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="PROTOCOL_HASH_MISMATCH"):
        acquire_dex(spec, staging, transport=transport)
    assert transport.requests == 0


def test_changed_manifest_file_fails_inspection(tmp_path):
    spec, staging, transport, _ = case(tmp_path)
    acquire_dex(spec, staging, transport=transport)
    destination = tmp_path / "published"
    publish_dex(staging, destination)
    (destination / "normalized/wrapped-sol.json").write_text("[]")
    with pytest.raises(ValueError, match="DATASET_HASH_MISMATCH"):
        inspect_dex(destination / "manifest.json")
