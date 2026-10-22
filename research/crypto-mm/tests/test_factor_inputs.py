import json
import hashlib
from pathlib import Path

import pytest

from crypto_mm.factors.inputs import validate_factor_protocol, verify_inputs, file_hash
from crypto_mm.factors.signals import SIGNALS


def protocol(tmp_path):
    package = Path(__file__).resolve().parents[1] / "src/crypto_mm"
    return dict(
        schema="competition.dex_factor_protocol.v1",
        dataset=dict(
            dataset_id="fixture",
            version="v1",
            source="dexpaprika",
            interval="1h",
            quote_currency="USD",
            selection="fixed_current",
            start="2025-01-01T00:00:00Z",
            end="2025-04-01T00:00:00Z",
            assets=[
                dict(
                    stable_id="wrapped-sol",
                    underlying_id="sol",
                    network="solana",
                    address="So11111111111111111111111111111111111111112",
                )
            ],
        ),
        manifest_file=str(tmp_path / "dataset/manifest.json"),
        source_commit="a" * 40,
        source_files=[
            dict(path=p.relative_to(package).as_posix(), sha256=file_hash(p))
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


def test_protocol_fixed_contract_and_duplicate_wrappers(tmp_path):
    value = protocol(tmp_path)
    validate_factor_protocol(value)
    value["dataset"]["assets"].append(
        value["dataset"]["assets"][0] | {"stable_id": "other"}
    )
    with pytest.raises(ValueError, match="INVALID_FACTOR_PROTOCOL"):
        validate_factor_protocol(value)


@pytest.mark.parametrize(
    "changes",
    [
        {"schema": "unknown"},
        {"minimum_overall": True},
        {"parameter_search": True},
        {"horizons": [1, 6]},
        {"unexpected": 1},
    ],
)
def test_unknown_or_changed_protocol_rejected(tmp_path, changes):
    with pytest.raises(ValueError, match="INVALID_FACTOR_PROTOCOL"):
        validate_factor_protocol(protocol(tmp_path) | changes)


def test_changed_scientific_source_rejected(tmp_path):
    value = protocol(tmp_path)
    value["source_files"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="FACTOR_SOURCE_MISMATCH"):
        verify_inputs(value)


def create_inputs(tmp_path, count=240):
    from test_factor_signals import rows

    value = protocol(tmp_path)
    root = tmp_path / "dataset"
    root.mkdir()
    normalized = root / "normalized.json"
    normalized.write_text(json.dumps(rows(count)))
    (root / "protocol.json").write_text(json.dumps(value))
    record = dict(
        path="normalized.json",
        sha256=file_hash(normalized),
        bytes=normalized.stat().st_size,
        role="normalized",
    )
    spec = dict(
        value["dataset"],
        schema="competition.dex_dataset_spec.v1",
        credential_file=str(tmp_path / "unused.env"),
        protocol_file=str(root / "protocol.json"),
        protocol_sha256=file_hash(root / "protocol.json"),
        budget={
            "requests": 100,
            "bytes": 52428800,
            "seconds": 900,
            "requests_per_minute": 20,
        },
    )
    manifest = dict(
        schema="competition.dex_dataset_manifest.v1",
        spec=spec,
        protocol_sha256=file_hash(root / "protocol.json"),
        files=[record],
        units={"price": "USD", "volume": "USD"},
        availability="bar_close_proxy_unverified",
        status="partial",
        dataset_id=spec["dataset_id"],
        version=spec["version"],
        spec_sha256=hashlib.sha256(
            json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        coverage=[],
        snapshots=[],
        budget={"requests": 0, "bytes": 0, "seconds": 0},
        created_at="2025-04-01T00:00:00Z",
        issues=[],
    )
    (root / "manifest.json").write_text(json.dumps(manifest))
    # Match dataset identity in rows for this independent leaf fixture.
    data = json.loads(normalized.read_text())
    for row in data:
        row["asset_id"] = "wrapped-sol"
    normalized.write_text(json.dumps(data))
    manifest["files"][0].update(
        sha256=file_hash(normalized), bytes=normalized.stat().st_size
    )
    (root / "manifest.json").write_text(json.dumps(manifest))
    return value


def test_unknown_manifest_fields_rejected(tmp_path):
    value = create_inputs(tmp_path)
    path = tmp_path / "dataset/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["unreviewed"] = True
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="INVALID_FACTOR_MANIFEST"):
        verify_inputs(value)


def test_input_hashes_and_mutation(tmp_path):
    value = create_inputs(tmp_path)
    inputs = verify_inputs(value)
    assert len(inputs["rows"]["wrapped-sol"]) == 240
    (tmp_path / "dataset/normalized.json").write_text("[]")
    with pytest.raises(ValueError, match="FACTOR_INPUT_HASH_MISMATCH"):
        verify_inputs(value)
