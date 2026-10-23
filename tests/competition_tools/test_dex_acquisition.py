import json
from datetime import datetime, timezone
from pathlib import Path

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
    from competition_tools.datasets.dex_protocol import SIGNALS

    package = Path(__file__).resolve().parents[2] / "research/crypto-mm/src/crypto_mm"
    protocol = dict(
        schema="competition.dex_factor_protocol.v1",
        dataset=dataset_identity(spec),
        manifest_file=str(tmp_path / "staging/manifest.json"),
        source_commit="a" * 40,
        source_files=[
            dict(path=p.relative_to(package).as_posix(), sha256=digest(p))
            for p in sorted((package / "factors").glob("*.py"))
        ],
        signals=SIGNALS,
        horizons=[6, 24],
        sampling=["all_valid", "non_overlapping"],
        role="retrospective",
        parameter_search=False,
        minimum_overall=30,
        minimum_slice=20,
        slices=3,
        slice_hours=720,
        groups=3,
        minimum_underlyings=9,
        minimum_per_group=3,
        availability="bar_close_proxy_unverified",
    )
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
            value = {
                "id": "wrong" if substitution else spec["assets"][0]["address"],
                "chain": spec["assets"][0]["network"],
            }
        return Response(json.dumps(value).encode())

    staging = tmp_path / "staging"
    transport = DexTransport(
        CAPS,
        key,
        staging / "requests-1.jsonl",
        opener=handler,
        clock=clock,
        sleep=clock.sleep,
        utc_now=lambda: datetime(2026, 10, 22, tzinfo=timezone.utc),
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


def test_receipt_includes_precollection_elapsed_time(tmp_path):
    spec, staging, transport, _ = case(tmp_path)
    transport.clock.now = 200
    receipt = acquire_dex(spec, staging, transport=transport)
    assert receipt["spent"]["seconds"] >= 200


def test_failed_network_resource_attempts_survive_resume(tmp_path):
    from urllib.error import URLError

    spec, staging, transport, calls = case(tmp_path)
    original = transport.opener

    def failed_network(request, timeout):
        if request.full_url.endswith("/networks"):
            calls.append(request.full_url)
            raise URLError("offline")
        return original(request, timeout)

    transport.opener = failed_network
    first = acquire_dex(spec, staging, transport=transport)
    remaining = spec["budget"] | {
        k: spec["budget"][k] - first["spent"][k]
        for k in ("requests", "bytes", "seconds")
    }
    remaining["seconds"] = int(remaining["seconds"])
    resumed = DexTransport(
        remaining,
        Path(spec["credential_file"]),
        staging / "requests-2.jsonl",
        opener=failed_network,
        clock=transport.clock,
        sleep=transport.sleep,
        utc_now=transport.utc_now,
    )
    second = acquire_dex(spec, staging, transport=resumed)
    assert second["issues"] == ["RETRIES_EXHAUSTED"]
    assert len([url for url in calls if url.endswith("/networks")]) == 2


def test_wrong_response_chain_blocks_before_candles(tmp_path):
    spec, staging, transport, calls = case(tmp_path)
    original = transport.opener

    def wrong_chain(request, timeout):
        if "/tokens/" in request.full_url:
            calls.append(request.full_url)
            return Response(
                json.dumps(
                    {"id": spec["assets"][0]["address"], "chain": "ethereum"}
                ).encode()
            )
        return original(request, timeout)

    transport.opener = wrong_chain
    receipt = acquire_dex(spec, staging, transport=transport)
    assert receipt["issues"] == ["TOKEN_IDENTITY_MISMATCH"]
    assert not any("/ohlcv?" in url for url in calls)


def test_incomplete_scientific_protocol_blocks_before_network(tmp_path):
    spec, staging, transport, calls = case(tmp_path)
    Path(spec["protocol_file"]).write_text(
        json.dumps({"dataset": dataset_identity(spec)})
    )
    spec["protocol_sha256"] = digest(Path(spec["protocol_file"]))
    with pytest.raises(ValueError, match="INVALID_FACTOR_PROTOCOL"):
        acquire_dex(spec, staging, transport=transport)
    assert calls == []


def test_finalization_time_cannot_produce_completed_over_budget_receipt(
    tmp_path, monkeypatch
):
    from competition_tools.datasets import dex_acquisition as acquisition

    spec, staging, transport, _ = case(tmp_path)
    original = acquisition.write_dex_manifest

    def expensive(*args):
        result = original(*args)
        transport.clock.now = 901
        return result

    monkeypatch.setattr(acquisition, "write_dex_manifest", expensive)
    receipt = acquire_dex(spec, staging, transport=transport)
    assert receipt["status"] == "blocked"
    assert "TIME_BUDGET" in receipt["issues"]


def test_pool_token_on_wrong_chain_blocks_before_candles(tmp_path):
    spec, staging, transport, calls = case(tmp_path)
    asset = spec["assets"][0]
    asset["pool_address"] = asset["address"]
    path = Path(spec["protocol_file"])
    protocol = json.loads(path.read_text())
    protocol["dataset"] = dataset_identity(spec)
    path.write_text(json.dumps(protocol))
    spec["protocol_sha256"] = digest(path)
    original = transport.opener

    def wrong_pool_token(request, timeout):
        if "/pools/" in request.full_url:
            calls.append(request.full_url)
            return Response(
                json.dumps(
                    dict(
                        id=asset["pool_address"],
                        chain=asset["network"],
                        tokens=[dict(id=asset["address"], chain="ethereum")],
                    )
                ).encode()
            )
        return original(request, timeout)

    transport.opener = wrong_pool_token
    receipt = acquire_dex(spec, staging, transport=transport)
    assert receipt["issues"] == ["POOL_IDENTITY_MISMATCH"]
    assert not any("/ohlcv?" in url for url in calls)
