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


@pytest.mark.parametrize(
    "mutation",
    ["omitted", "duplicate", "extra", "coverage", "receipt", "plan", "rehashed"],
)
def test_acquired_manifest_cannot_redefine_verified_inputs(tmp_path, mutation):
    from competition_tools.datasets.binance_daily_acquisition import (
        acquire_daily_extension,
        inspect_daily_extension,
    )

    config, plan = prepared(tmp_path)
    out = tmp_path / "acquired"
    acquire_daily_extension(config, plan, out, transport=ArchiveTransport())
    manifest = out / "manifest.json"
    value = json.loads(manifest.read_text())
    if mutation == "omitted":
        value["files"] = [
            r for r in value["files"] if r["path"] != "normalized/BTCUSDT.csv"
        ]
        file = out / "normalized/BTCUSDT.csv"
        file.write_text(file.read_text().replace("1.5", "1.75"))
    elif mutation == "duplicate":
        value["files"].append(value["files"][0])
    elif mutation == "extra":
        (out / "normalized/UNKNOWN.csv").write_text("unlisted")
    elif mutation == "coverage":
        del value["coverage"]["BTCUSDT"]
    elif mutation == "receipt":
        value["receipt"]["attempts"] = 0
        value["receipt"]["collected_at"] = "2000-01-01T00:00:00+00:00"
    elif mutation == "plan":
        value["plan"]["parent_status"] = "acquired"
    else:
        file = out / "normalized/BTCUSDT.csv"
        file.write_text(file.read_text().replace("1.5", "1.75"))
        record = next(
            r for r in value["files"] if r["path"] == "normalized/BTCUSDT.csv"
        )
        record.update(sha256=digest(file), bytes=file.stat().st_size)
    manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        inspect_daily_extension(manifest)
    from competition_tools.evaluation.observation_preparation import prepare_observation

    # Integrity must fail before consulting the existing protocol or writing
    # any warmup, even when an otherwise valid CSV omitted from the inventory
    # would be read independently by that consumer.
    with pytest.raises(ValueError):
        prepare_observation(
            config,
            manifest,
            tmp_path / "warmup",
            parent_registry=tmp_path / "unavailable-parent-registry",
        )
    assert not (tmp_path / "warmup").exists()


def test_successive_extensions_retain_ancestry_and_reservation_owner(tmp_path):
    from competition_tools.datasets.binance_daily_acquisition import (
        acquire_daily_extension,
        inspect_daily_extension,
        reservation_path,
    )
    from competition_tools.datasets.binance_daily_spec import (
        freeze_daily_extension,
        parent_rows,
    )

    config, plan_path = prepared(tmp_path)
    plan = json.loads(plan_path.read_text())
    out = tmp_path / "nested/first"
    acquire_daily_extension(config, plan_path, out, transport=ArchiveTransport())
    first = out / "manifest.json"
    assert inspect_daily_extension(first)["parent_status"] == "partial"
    next_spec = dict(
        schema="competition.binance_daily_extension.v1",
        start="2025-01-03",
        end="2025-01-03",
        parent_sha256=digest(first),
    )
    second_plan = freeze_daily_extension(
        next_spec,
        first,
        tmp_path / "second-plan",
        now=datetime(2025, 1, 4, tzinfo=timezone.utc),
    )
    assert reservation_path(second_plan).parent == reservation_path(plan).parent
    assert second_plan["parent_status"] == "partial"
    second = tmp_path / "another/second"
    receipt = acquire_daily_extension(
        config,
        tmp_path / "second-plan/plan.json",
        second,
        transport=ArchiveTransport(),
    )
    assert receipt["status"] == "acquired"
    value = inspect_daily_extension(second / "manifest.json")
    assert value["plan"]["parent_sha256"] == digest(first)
    assert value["coverage"]["BTCUSDT"] == dict(
        rows=3, start="2025-01-01", end="2025-01-03"
    )
    source, tables = parent_rows(second / "manifest.json")
    assert source["spec"]["source"] == "binance_spot"
    assert source["status"] == "partial"
    assert [r[0] for r in tables["BTCUSDT"]] == [
        "2025-01-01",
        "2025-01-02",
        "2025-01-03",
    ]
    (first.parent / "normalized/BTCUSDT.csv").write_text("changed ancestor")
    with pytest.raises(ValueError):
        inspect_daily_extension(second / "manifest.json")
