"""Acquisition reservations survive destination changes and uncertain spend."""

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from competition_tools.datasets.storage import digest
from competition_tools.team.config import TeamConfig
from test_binance_daily_spec import parent_fixture


def prepared(tmp_path):
    from competition_tools.datasets.binance_daily_spec import freeze_daily_extension

    parent, spec = parent_fixture(tmp_path)
    spec["end"] = "2025-01-02"
    freeze_daily_extension(
        spec, parent, tmp_path / "plan", now=datetime(2025, 1, 3, tzinfo=timezone.utc)
    )
    return TeamConfig(tmp_path, tmp_path / "env"), tmp_path / "plan/plan.json"


class ArchiveTransport:
    def fetch(self, url, *, max_bytes, timeout):
        name = url.rsplit("/", 1)[1].removesuffix(".CHECKSUM")
        data = io.BytesIO()
        timestamp = (
            int(
                datetime.fromisoformat(name[-14:-4])
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
            * 1_000_000
        )
        with zipfile.ZipFile(data, "w") as z:
            z.writestr(
                zipfile.ZipInfo(
                    name.removesuffix(".zip") + ".csv", (2020, 1, 1, 0, 0, 0)
                ),
                f"{timestamp},1,2,.5,1.5,10,0,0,0,0,0,0\n",
            )
        body = data.getvalue()
        if url.endswith("CHECKSUM"):
            body = f"{hashlib.sha256(body).hexdigest()}  {name}".encode()
        assert 0 < timeout <= 600
        assert len(body) <= max_bytes
        return 200, body


def test_complete_extension_and_inspect_hashes(tmp_path):
    from competition_tools.datasets.binance_daily_acquisition import (
        acquire_daily_extension,
        inspect_daily_extension,
    )

    config, plan = prepared(tmp_path)
    result = acquire_daily_extension(
        config, plan, tmp_path / "result", transport=ArchiveTransport()
    )
    assert result["status"] == "acquired"
    assert result["attempts"] == 16
    assert result["accepted_research"] is False
    manifest = tmp_path / "result/manifest.json"
    from jsonschema import Draft202012Validator

    schema_root = Path(__file__).resolve().parents[3] / "schemas/datasets"
    for name, value in [
        ("plan", json.loads(plan.read_text())),
        ("receipt", result),
        ("manifest", json.loads(manifest.read_text())),
    ]:
        validator = Draft202012Validator(
            json.loads(
                (schema_root / f"binance-daily-{name}.v1.schema.json").read_text()
            )
        )
        assert not list(validator.iter_errors(value))
        assert list(validator.iter_errors(value | {"credential_file": "sentinel"}))
    assert inspect_daily_extension(manifest)["coverage"]["BTCUSDT"]["rows"] == 2
    (tmp_path / "result/normalized/BTCUSDT.csv").write_text("tampered")
    with pytest.raises(ValueError, match="HASH"):
        inspect_daily_extension(manifest)
    assert digest(plan)


def test_uncertain_spend_cannot_reset_with_new_output_or_config(tmp_path):
    from competition_tools.datasets.binance_daily_acquisition import (
        acquire_daily_extension,
    )

    config, plan = prepared(tmp_path)

    class Interrupted:
        def fetch(self, *args, **kwargs):
            raise TimeoutError("private-sentinel")

    result = acquire_daily_extension(
        config, plan, tmp_path / "first", transport=Interrupted()
    )
    assert result["status"] == "blocked"


def test_full_31_day_plan_and_completed_reservation_cannot_repeat(tmp_path):
    from competition_tools.datasets.binance_daily_spec import freeze_daily_extension
    from competition_tools.datasets.binance_daily_acquisition import (
        acquire_daily_extension,
    )

    parent, spec = parent_fixture(tmp_path)
    freeze_daily_extension(
        spec, parent, tmp_path / "plan", now=datetime(2025, 2, 2, tzinfo=timezone.utc)
    )
    config = TeamConfig(tmp_path, tmp_path / "env")
    plan = tmp_path / "plan/plan.json"
    result = acquire_daily_extension(
        config, plan, tmp_path / "out", transport=ArchiveTransport()
    )
    assert result["attempts"] == 496
    assert result["status"] == "acquired"
    with pytest.raises(ValueError, match="RESERVATION"):
        acquire_daily_extension(
            config, plan, tmp_path / "other", transport=ArchiveTransport()
        )
    assert "private-sentinel" not in json.dumps(result)
    with pytest.raises(ValueError, match="RESERVATION"):
        acquire_daily_extension(
            TeamConfig(tmp_path / "different", config.environment_root),
            plan,
            tmp_path / "second",
            transport=ArchiveTransport(),
        )
    assert not (tmp_path / "second").exists()


def test_attempt_error_body_is_charged(tmp_path):
    from competition_tools.datasets.binance_daily_acquisition import (
        acquire_daily_extension,
    )

    config, plan = prepared(tmp_path)

    class ErrorResponse:
        def fetch(self, *args, **kwargs):
            return 429, b"limited"

    result = acquire_daily_extension(
        config, plan, tmp_path / "error", transport=ErrorResponse()
    )
    assert result["attempts"] == 1
    assert result["transferred_bytes"] == 7
    assert result["status"] == "blocked"


def test_finalization_cannot_claim_success_after_deadline(tmp_path, monkeypatch):
    from competition_tools.datasets import binance_daily_acquisition as module

    config, plan = prepared(tmp_path)
    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    real_write = module.write_json

    def delayed_write(path, value):
        real_write(path, value)
        if path.name == "manifest.json":
            clock[0] = 601.0

    monkeypatch.setattr(module, "write_json", delayed_write)
    result = module.acquire_daily_extension(
        config, plan, tmp_path / "late", transport=ArchiveTransport()
    )
    assert result["status"] == "blocked"
    assert not (tmp_path / "late/manifest.json").exists()


def test_blocked_receipt_is_inspectable_but_tampering_is_rejected(tmp_path):
    from competition_tools.datasets.binance_daily_acquisition import (
        acquire_daily_extension,
        inspect_daily_extension,
    )

    config, plan = prepared(tmp_path)

    class Interrupted:
        def fetch(self, *args, **kwargs):
            raise TimeoutError

    acquire_daily_extension(config, plan, tmp_path / "blocked", transport=Interrupted())
    receipt = tmp_path / "blocked/receipt.json"
    assert inspect_daily_extension(receipt)["status"] == "blocked"
    value = json.loads(receipt.read_text())
    value["attempts"] = 0
    receipt.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        inspect_daily_extension(receipt)
