import csv
import json
from pathlib import Path

import pytest

from competition_tools.datasets.databento_acquisition import acquire, verify_manifest
from competition_tools.datasets.databento_spec import SYMBOLS, pilot_spec


@pytest.fixture(autouse=True)
def isolated_authorization(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace.toml"
    workspace.write_text(
        "data_root = " + json.dumps(str(tmp_path / "authority")) + "\n"
    )
    monkeypatch.setenv("WORKSPACE_CONFIG", str(workspace))


class FakeTransport:
    def __init__(self, fail=False, cost="0.004"):
        self.fail, self.cost = fail, cost
        self.downloads = self.metadata = 0

    def check_time(self):
        return 100

    def spent(self):
        return {
            "metadata_requests": self.metadata,
            "download_requests": self.downloads,
            "bytes": 1,
            "seconds": 1,
        }

    def get_metadata(self, method, params):
        self.metadata += 1
        if method == "metadata.get_cost":
            return self.cost
        if method == "metadata.get_record_count":
            return 10
        if method == "metadata.get_billable_size":
            return 560
        if method == "metadata.list_unit_prices":
            return [{"mode": "historical-streaming", "unit_prices": {"ohlcv-1d": 20}}]
        if method == "symbology.resolve":
            return {
                "result": {
                    s: [{"d0": "2025-01-01", "d1": "2026-01-01", "s": str(i + 1)}]
                    for i, s in enumerate(SYMBOLS)
                },
                "not_found": [],
                "partial": [],
            }
        raise AssertionError(method)

    def download_csv(self, params, destination):
        self.downloads += 1
        if self.fail:
            raise ValueError("PROVIDER_CONNECTION_FAILED")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(
                [
                    "ts_event",
                    "rtype",
                    "publisher_id",
                    "instrument_id",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "symbol",
                ]
            )
            for i, symbol in enumerate(SYMBOLS):
                writer.writerow(
                    [
                        "2025-01-02T00:00:00.000000000Z",
                        35,
                        1,
                        i + 1,
                        100,
                        102,
                        99,
                        101,
                        1000,
                        symbol,
                    ]
                )


def test_interrupted_download_cannot_retry(tmp_path):
    spec = pilot_spec(tmp_path / "key.env")
    destination = tmp_path / "pilot"
    t = FakeTransport(fail=True)
    result = acquire(spec, destination, transport=t)
    assert result["status"] == "blocked"
    assert t.downloads == 1
    with pytest.raises(ValueError):
        acquire(spec, destination, transport=t)
    with pytest.raises(ValueError, match="ATTEMPT"):
        acquire(spec, tmp_path / "another-version", transport=t)
    assert t.downloads == 1


def test_authorization_survives_destination_parent_change(tmp_path):
    t = FakeTransport(fail=True)
    spec = pilot_spec(tmp_path / "key.env")
    acquire(spec, tmp_path / "first" / "pilot", transport=t)
    with pytest.raises(ValueError, match="ATTEMPT"):
        acquire(spec, tmp_path / "second" / "pilot", transport=t)
    assert t.downloads == 1


def test_forged_acquired_receipt_without_data_rejected(tmp_path):
    from competition_tools.datasets.databento_acquisition import digest

    result = acquire(
        pilot_spec(tmp_path / "key.env"),
        tmp_path / "pilot",
        transport=FakeTransport(fail=True),
    )
    path = Path(result["manifest"])
    manifest = json.loads(path.read_text())
    manifest["receipt"]["status"] = "acquired"
    manifest["receipt"]["issue_codes"] = []
    receipt = path.parent / "receipt.json"
    receipt.write_text(json.dumps(manifest["receipt"]))
    for record in manifest["files"]:
        if record["path"] == "receipt.json":
            record["sha256"] = digest(receipt)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        verify_manifest(path)


def test_acquisition_observed_time_is_after_download(tmp_path, monkeypatch):
    from datetime import datetime, timezone, timedelta
    from competition_tools.datasets import databento_acquisition as module

    clock = [datetime(2026, 10, 23, tzinfo=timezone.utc)]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    class Download(FakeTransport):
        def download_csv(self, params, destination):
            super().download_csv(params, destination)
            clock[0] += timedelta(seconds=5)

    monkeypatch.setattr(module, "datetime", Clock)
    result = acquire(
        pilot_spec(tmp_path / "key.env"), tmp_path / "pilot", transport=Download()
    )
    assert result["observed_at"] > result["started_at"]


def test_high_quote_stops_before_download(tmp_path):
    t = FakeTransport(cost="0.11")
    result = acquire(pilot_spec(tmp_path / "key.env"), tmp_path / "pilot", transport=t)
    assert result["status"] == "blocked"
    assert t.downloads == 0


def test_calendar_and_immutable_inputs(tmp_path):
    result = acquire(
        pilot_spec(tmp_path / "key.env"), tmp_path / "pilot", transport=FakeTransport()
    )
    path = Path(result["manifest"])
    manifest = verify_manifest(path)
    assert manifest["accepted_research"] is False
    assert manifest["spec"]["price_basis"] == "raw"
    assert "LISTING_CALENDAR_UNVERIFIED" in manifest["receipt"]["issue_codes"]
    raw = path.parent / "raw/bars.csv"
    raw.write_text("changed")
    with pytest.raises(ValueError, match="HASH"):
        verify_manifest(path)


def test_wrong_dated_mapping_blocks_consumption(tmp_path):
    class Wrong(FakeTransport):
        def get_metadata(self, method, params):
            data = super().get_metadata(method, params)
            if method == "symbology.resolve":
                data["result"]["SPY"][0]["s"] = "999"
            return data

    result = acquire(
        pilot_spec(tmp_path / "key.env"), tmp_path / "pilot", transport=Wrong()
    )
    assert result["status"] == "blocked"
    assert "IDENTITY" in result["issue_codes"][0]
