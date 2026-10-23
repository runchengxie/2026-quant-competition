"""Frozen daily plans retain exact parent identity and resource bounds."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from competition_tools.datasets.storage import digest, write_manifest


def parent_fixture(tmp_path):
    from competition_tools.datasets.binance_daily import PRODUCTS

    root = tmp_path / "parent"
    (root / "normalized").mkdir(parents=True)
    (root / ".dataset-owner").write_text("competition.dataset.v1")
    spec = dict(
        schema="competition.dataset_spec.v1",
        dataset_id="fixture",
        version="v1",
        source="binance_spot",
        market="crypto",
        products=sorted(PRODUCTS),
        quote_currency="USDT",
        start="2025-01-01",
        end="2025-01-01",
        timezone="UTC",
        calendar="365",
        price_basis="raw",
        universe_status="fixed_current",
        budget=dict(requests=20, bytes=10000, seconds=600),
    )
    for p in PRODUCTS:
        (root / "normalized" / f"{p}.csv").write_text(
            "date,open,high,low,close,volume\n2025-01-01,1,2,.5,1,1\n"
        )
    write_manifest(spec, root)
    manifest = root / "manifest.json"
    extension = dict(
        schema="competition.binance_daily_extension.v1",
        start="2025-01-02",
        end="2025-02-01",
        parent_sha256=digest(manifest),
    )
    return manifest, extension


def test_exact_resource_plan_and_immutable_parent(tmp_path):
    from competition_tools.datasets.binance_daily_spec import freeze_daily_extension

    parent, spec = parent_fixture(tmp_path)
    plan = freeze_daily_extension(
        spec, parent, tmp_path / "out", now=datetime(2025, 2, 2, tzinfo=timezone.utc)
    )
    assert len(plan["resources"]) == 496
    assert plan["budget"] == dict(
        attempts=600,
        transferred_bytes=134217728,
        expanded_bytes=268435456,
        per_zip_bytes=4194304,
        seconds=600,
    )
    assert plan["parent_status"] == "partial"
    assert plan["start"] == "2025-01-02"
    assert json.loads((tmp_path / "out/plan.json").read_text()) == plan
    with pytest.raises(FileExistsError):
        freeze_daily_extension(
            spec,
            parent,
            tmp_path / "out",
            now=datetime(2025, 2, 2, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize(
    "kind", ["too_long", "incomplete", "hash", "already_present", "source"]
)
def test_invalid_extension_does_not_publish(tmp_path, kind):
    from competition_tools.datasets.binance_daily_spec import freeze_daily_extension

    parent, spec = parent_fixture(tmp_path)
    output = tmp_path / "out"
    if kind == "too_long":
        spec["end"] = "2025-02-02"
    elif kind == "hash":
        spec["parent_sha256"] = "0" * 64
    elif kind == "already_present":
        spec["start"] = "2025-01-01"
    elif kind == "source":
        (tmp_path / ".git").mkdir()
    now = datetime(2025, 2, 1 if kind == "incomplete" else 3, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        freeze_daily_extension(spec, parent, output, now=now)
    assert not output.exists()


def test_extension_schema_rejects_added_credentials(tmp_path):
    from jsonschema import Draft202012Validator

    schema = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "schemas/datasets/binance-daily-extension.v1.schema.json"
        ).read_text()
    )
    _, spec = parent_fixture(tmp_path)
    validator = Draft202012Validator(schema)
    assert not list(validator.iter_errors(spec))
    assert list(validator.iter_errors(spec | {"credential_file": "secret"}))
