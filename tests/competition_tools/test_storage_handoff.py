import json
import hashlib

import pytest

from competition_tools.datasets.storage_handoff import (
    build_manifest,
    copy_manifest,
    verify_manifest,
)


def completed(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "parquet").mkdir()
    (source / "parquet/a.parquet").write_bytes(b"example")
    summary = {
        "status": "complete",
        "scope": "full",
        "rows": 10,
        "volume": 20,
        "parts": 1,
        "all_columns_logical_sha256_readback_both_stages": True,
        "input_file_sha256_verified": True,
        "all_parquet_pages_checksum_verified": True,
        "source_manifest_unchanged": True,
        "strict_per_security_year_time_order": True,
    }
    (source / "summary.json").write_text(json.dumps(summary))
    (source / "progress.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "phase": "complete",
                "expected_rows": 10,
                "final_verified_rows": 10,
            }
        )
    )
    digest = hashlib.sha256(b"example").hexdigest()
    (source / "file_index.csv").write_text(
        f"file,rows,volume,bytes,sha256\nparquet/a.parquet,10,20,7,{digest}\n"
    )
    return source


def test_running_conversion_cannot_produce_handoff(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "progress.json").write_text('{"status":"running"}')
    with pytest.raises(ValueError, match="not complete"):
        build_manifest(source)


def test_manifest_freezes_only_final_files_and_detects_changed_bytes(tmp_path):
    source = completed(tmp_path)
    (source / "staging").mkdir()
    (source / "staging/not-final.parquet").write_bytes(b"partial")
    manifest = build_manifest(source)
    assert not any("staging" in item["path"] for item in manifest["files"])
    verify_manifest(manifest)
    (source / "parquet/a.parquet").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        verify_manifest(manifest)


def test_manifest_refuses_escaping_paths_or_row_mismatch(tmp_path):
    source = completed(tmp_path)
    (source / "file_index.csv").write_text(
        "file,rows,volume,bytes,sha256\n../outside.parquet,10,20,7,x\n"
    )
    with pytest.raises(ValueError):
        build_manifest(source)
    (source / "file_index.csv").write_text(
        "file,rows,volume,bytes,sha256\nparquet/a.parquet,9,20,7,x\n"
    )
    with pytest.raises(ValueError, match="conservation"):
        build_manifest(source)


def test_copy_publishes_verified_new_directory_and_preserves_source(tmp_path):
    source = completed(tmp_path)
    manifest = build_manifest(source)
    destination = tmp_path / "dated-copy"
    copy_manifest(manifest, destination)
    assert (destination / "parquet/a.parquet").read_bytes() == b"example"
    assert (source / "parquet/a.parquet").read_bytes() == b"example"
    assert (destination / "transfer-receipt.json").is_file()
    with pytest.raises(FileExistsError):
        copy_manifest(manifest, destination)
