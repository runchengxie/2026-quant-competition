"""Refresh keeps its parent immutable and rebuilds revised price scales."""

import hashlib

import pytest
from competition_tools.datasets.daily_refresh import refresh_daily
from competition_tools.datasets.daily_storage import write_daily_manifest
from test_daily_broker import run, Clock, Client


def test_refresh_preserves_parent_and_lineage(tmp_path, monkeypatch):
    spec, receipt, _, _ = run(tmp_path, monkeypatch)
    root = tmp_path / "stage"
    write_daily_manifest(spec, root, receipt)
    parent = root / "manifest.json"
    before = parent.read_bytes()
    clock = Clock()

    class Session:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return Client(clock)

        def __exit__(self, *a):
            pass

    refreshed = refresh_daily(
        spec | {"version": "v2"},
        parent,
        tmp_path / "new",
        session_factory=Session,
        clock=clock,
        sleep=clock.sleep,
    )
    assert parent.read_bytes() == before
    assert refreshed["parent_manifest_sha256"] == hashlib.sha256(before).hexdigest()
    assert refreshed["status"] == "acquired"
    assert refreshed["revisions"] == []
    assert (
        refreshed["adjustment_evidence"]["out_of_overlap_revisions"] == "not_verified"
    )
    assert (
        refreshed["adjustment_evidence"]["last_full_verification"]
        == receipt["adjustment_evidence"]["last_full_verification"]
    )


def test_refresh_rejects_identity_change_and_same_version(tmp_path, monkeypatch):
    spec, receipt, _, _ = run(tmp_path, monkeypatch)
    write_daily_manifest(spec, tmp_path / "stage", receipt)
    for change in (
        {},
        {"version": "v2", "end": "2024-07-03"},
        {"version": "v2", "start": "2024-07-02"},
        {"version": "v2", "dataset_id": "other"},
    ):
        with pytest.raises(ValueError):
            refresh_daily(
                spec | change,
                tmp_path / "stage/manifest.json",
                tmp_path / "new",
                session_factory=None,
                clock=Clock(),
                sleep=lambda x: None,
            )
    assert not (tmp_path / "new").exists()


def test_overlap_revision_rebuilds_entire_instrument(tmp_path, monkeypatch):
    import csv

    spec, receipt, _, _ = run(tmp_path, monkeypatch)
    write_daily_manifest(spec, tmp_path / "stage", receipt)
    clock = Clock()

    class Revised(Client):
        def reqHistoricalData(self, contract, **kwargs):
            bars = super().reqHistoricalData(contract, **kwargs)
            if contract.symbol == "AAPL":
                for bar in bars:
                    bar.open, bar.high, bar.low, bar.close = 50, 51, 49.5, 50.5
            return bars

    class Session:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return Revised(clock)

        def __exit__(self, *a):
            pass

    refreshed = refresh_daily(
        spec | {"version": "v2"},
        tmp_path / "stage/manifest.json",
        tmp_path / "new",
        session_factory=Session,
        clock=clock,
        sleep=clock.sleep,
    )
    assert refreshed["status"] == "acquired"
    assert refreshed["revisions"] == [
        {"product": "AAPL", "action": "full_rebuild", "reason": "OVERLAP_CHANGED"}
    ]
    rows = list(csv.DictReader((tmp_path / "new/normalized/AAPL.csv").open()))
    assert all(float(r["close"]) == 50.5 for r in rows)
    assert receipt["coverage"]["AAPL"]["bars"] == len(rows)


def test_refresh_does_not_copy_parent_over_the_byte_budget(tmp_path, monkeypatch):
    spec, receipt, _, _ = run(tmp_path, monkeypatch)
    write_daily_manifest(spec, tmp_path / "stage", receipt)
    spec = spec | {"version": "v2", "budget": spec["budget"] | {"bytes": 1}}
    with pytest.raises(ValueError, match="REFRESH_BASE_EXCEEDS_BYTE_BUDGET"):
        refresh_daily(
            spec,
            tmp_path / "stage/manifest.json",
            tmp_path / "new",
            session_factory=None,
            clock=Clock(),
            sleep=lambda x: None,
        )
    assert not (tmp_path / "new").exists()


def test_revision_replaces_prices_older_than_five_session_overlap(
    tmp_path, monkeypatch
):
    import csv
    from datetime import date
    from types import SimpleNamespace
    from competition_tools.datasets.daily_broker import collect_daily

    spec, _, _, clock = run(tmp_path / "fixture", monkeypatch)
    dates = [
        "2023-01-03",
        "2024-07-01",
        "2024-07-02",
        "2024-07-03",
        "2024-07-05",
        "2024-07-08",
    ]
    monkeypatch.setattr(
        "competition_tools.datasets.daily_broker.completed_sessions",
        lambda *a, **k: {
            "sessions": dates,
            "calendar_name": "XNYS",
            "package_version": "synthetic",
            "schedule_sha256": "b" * 64,
            "latest_completed_session": dates[-1],
        },
    )
    revised = False

    class History(Client):
        def reqHistoricalData(self, contract, **kwargs):
            close = 50.0 if revised and contract.symbol == "AAPL" else 100.0
            return [
                SimpleNamespace(
                    date=date.fromisoformat(d),
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    volume=5,
                )
                for d in dates
            ]

    class Session:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return History(clock)

        def __exit__(self, *a):
            pass

    spec = spec | {"start": "2023-01-01", "end": dates[-1]}
    receipt = collect_daily(
        spec,
        tmp_path / "parent",
        session_factory=Session,
        clock=clock,
        sleep=clock.sleep,
    )
    assert receipt["status"] == "acquired"
    write_daily_manifest(spec, tmp_path / "parent", receipt)
    revised = True
    child = refresh_daily(
        spec | {"version": "v2"},
        tmp_path / "parent/manifest.json",
        tmp_path / "child",
        session_factory=Session,
        clock=clock,
        sleep=clock.sleep,
    )
    assert child["status"] == "acquired"
    rows = list(csv.DictReader((tmp_path / "child/normalized/AAPL.csv").open()))
    assert rows[0]["date"] == "2023-01-03"
    assert float(rows[0]["close"]) == 50
    assert child["revisions"] == [
        {"product": "AAPL", "action": "full_rebuild", "reason": "OVERLAP_CHANGED"}
    ]
