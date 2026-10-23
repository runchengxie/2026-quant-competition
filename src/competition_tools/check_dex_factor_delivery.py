"""Actual root/leaf CLI delivery using deterministic synthetic hourly inputs only."""

import argparse
import io
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from competition_tools.datasets.dex_acquisition import acquire_dex
from competition_tools.datasets.dex_storage import publish_dex
from competition_tools.datasets.dex_transport import DexTransport
from competition_tools.datasets.dex_spec import (
    CAPS,
    dataset_identity,
    safe_path,
    utc_hour,
)
from competition_tools.datasets.storage import digest, write_json
from competition_tools.team.config import TeamConfig
from competition_tools.team.factors import SIGNALS, execute


def synthetic_delivery(leaf_python, output_root):
    leaf_python, output = Path(leaf_python).resolve(), safe_path(output_root)
    expected = leaf_python.parents[1].name
    if expected != "crypto-mm":
        raise ValueError("LEAF_ENVIRONMENT_MUST_BE_NAMED_CRYPTO_MM")
    output.mkdir(parents=True, exist_ok=False)
    repository = Path(__file__).resolve().parents[2]
    package = repository / "research/crypto-mm/src/crypto_mm"
    source_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    ).stdout.strip()
    credential = output / "synthetic.env"
    credential.write_text("DEXPAPRIKA_API_KEY=synthetic-fixture-only\n")
    spec = dict(
        schema="competition.dex_dataset_spec.v1",
        dataset_id="synthetic-dex-delivery",
        version="v1",
        source="dexpaprika",
        interval="1h",
        quote_currency="USD",
        selection="fixed_current",
        start="2025-01-01T00:00:00Z",
        end="2025-04-01T00:00:00Z",
        assets=[
            dict(
                stable_id="synthetic-sol",
                underlying_id="sol",
                network="solana",
                address="So11111111111111111111111111111111111111112",
            )
        ],
        credential_file=str(credential),
        protocol_file=str(output / "protocol.json"),
        protocol_sha256="0" * 64,
        budget=CAPS,
    )
    destination = output / "dataset"
    protocol = dict(
        schema="competition.dex_factor_protocol.v1",
        dataset=dataset_identity(spec),
        manifest_file=str(destination / "manifest.json"),
        source_commit=source_commit,
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
    write_json(output / "protocol.json", protocol)
    spec["protocol_sha256"] = digest(output / "protocol.json")

    class Response(io.BytesIO):
        headers = {"Content-Type": "application/json"}

    time = [0.0]
    calls = [0]

    def opener(request, timeout):
        calls[0] += 1
        parsed = urlsplit(request.full_url)
        if parsed.path == "/usage":
            now = datetime.now(timezone.utc)
            begin = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = (begin + timedelta(days=32)).replace(day=1)
            value = dict(
                plan="pro",
                requests_used=calls[0],
                requests_left=5000000 - calls[0],
                period_started_at=begin.isoformat(),
                period_ends_at=end.isoformat(),
            )
        elif parsed.path == "/networks":
            value = [{"id": "solana"}]
        elif parsed.path.endswith("/ohlcv"):
            query = parse_qs(parsed.query)
            first, end = utc_hour(query["start"][0]), utc_hour(query["end"][0])
            value = []
            while first < end:
                offset = int((first - utc_hour(spec["start"])).total_seconds() / 3600)
                close = 100 + offset * 0.01 + (offset % 17) * 0.1
                value.append(
                    dict(
                        time_open=first.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        time_close=(first + timedelta(hours=1)).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        open=close,
                        high=close + 1,
                        low=close - 1,
                        close=close,
                        volume=100 + offset % 23,
                    )
                )
                first += timedelta(hours=1)
        else:
            value = {"id": spec["assets"][0]["address"], "chain": "solana"}
        return Response(json.dumps(value).encode())

    staging = destination.with_name(destination.name + ".partial")
    transport = DexTransport(
        CAPS,
        credential,
        staging / "requests-1.jsonl",
        opener=opener,
        clock=lambda: time[0],
        sleep=lambda seconds: time.__setitem__(0, time[0] + seconds),
    )
    receipt = acquire_dex(spec, staging, transport=transport)
    if receipt["status"] != "completed":
        raise ValueError("SYNTHETIC_ACQUISITION_FAILED")
    publish_dex(staging, destination)
    config = TeamConfig(output / "data", leaf_python.parents[2])
    result = execute(config, output / "protocol.json", output / "research")
    if result["status"] != "completed":
        raise ValueError("SYNTHETIC_FACTOR_DELIVERY_FAILED")
    return dict(
        status="completed",
        synthetic=True,
        http_requests=0,
        fixture_attempts=transport.requests,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leaf-python", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    # Exercise inherited-key removal. This sentinel never authenticates a request.
    os.environ["DEXPAPRIKA_API_KEY"] = "synthetic-inherited-sentinel"
    try:
        result = synthetic_delivery(args.leaf_python, args.output_root)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError):
        print(json.dumps(dict(status="blocked", reason="SYNTHETIC_DELIVERY_FAILED")))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
