"""Synthetic examples must be reproducible and must never replace user data."""

import json

import polars as pl
import pytest

from crypto_mm.demo import build_demo_data


def test_demo_writes_nine_explicitly_synthetic_files(tmp_path):
    raw = tmp_path / "raw_data"
    paths = build_demo_data(raw)
    assert len(paths) == 9
    assert all(p.is_relative_to(raw) and p.suffix == ".parquet" for p in paths)
    assert all(pl.read_parquet(p).height == 121 for p in paths)
    metadata = json.loads((tmp_path / "demo-manifest.json").read_text())
    assert metadata["synthetic"] is True
    assert metadata["purpose"] == "software demonstration only"


def test_demo_refuses_to_overwrite_any_existing_data(tmp_path):
    raw = tmp_path / "raw_data"
    raw.mkdir()
    existing = raw / "keep.txt"
    existing.write_text("user data")
    with pytest.raises(FileExistsError):
        build_demo_data(raw)
    assert existing.read_text() == "user data"
