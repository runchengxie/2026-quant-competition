"""Bounded historical collection preserves the requested pool and bytes."""

import json
from datetime import date
from types import SimpleNamespace

import pytest
from competition_tools.datasets.daily_broker import collect_daily
from competition_tools.datasets.daily_storage import (
    write_daily_manifest,
    verify_daily_manifest,
)
from test_daily_spec import daily_spec


class Clock:
    def __init__(self):
        self.value = 0

    def __call__(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class Client:
    def __init__(self, clock, missing=False, bad=False):
        self.clock = clock
        self.starts = []
        self.missing = missing
        self.bad = bad

    def qualifyContracts(self, contract):
        self.starts.append(self.clock())
        contract.conId = 42 if contract.symbol == "AAPL" else 43
        return [contract]

    def reqHistoricalData(self, contract, **kwargs):
        self.starts.append(self.clock())
        assert kwargs["keepUpToDate"] is False
        assert kwargs["useRTH"] is True
        assert kwargs["barSizeSetting"] == "1 day"
        assert kwargs["endDateTime"] == "20240706-04:00:00"
        if self.missing and contract.symbol == "AAPL":
            return []
        return [
            SimpleNamespace(
                date=date(2024, 7, day),
                open=100,
                high=102,
                low=99,
                close=float("nan") if self.bad else 101,
                volume=5,
            )
            for day in [1, 2, 3, 5]
        ]


def run(tmp_path, monkeypatch, *, missing=False, bad=False, budget=None):
    spec = daily_spec()
    if budget is not None:
        spec["budget"] = budget
    clock = Clock()
    client = Client(clock, missing, bad)
    monkeypatch.setattr(
        "competition_tools.datasets.daily_broker.completed_sessions",
        lambda *a, **k: {
            "sessions": ["2024-07-01", "2024-07-02", "2024-07-03", "2024-07-05"],
            "calendar_name": "XNYS",
            "package_version": "synthetic",
            "schedule_sha256": "a" * 64,
            "latest_completed_session": "2024-07-05",
        },
    )

    class Session:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return client

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(
        "competition_tools.datasets.daily_broker._stock",
        lambda s: SimpleNamespace(
            symbol=s["symbol"],
            exchange=s["exchange"],
            currency=s["currency"],
            secType="STK",
            conId=0,
        ),
    )
    receipt = collect_daily(
        spec,
        tmp_path / "stage",
        session_factory=Session,
        clock=clock,
        sleep=clock.sleep,
    )
    return spec, receipt, client, clock


def test_complete_data_is_spaced_and_manifest_is_verifiable(tmp_path, monkeypatch):
    spec, receipt, client, clock = run(tmp_path, monkeypatch)
    assert receipt["status"] == "acquired"
    assert receipt["requests"] == 4
    assert all(b - a >= 10 for a, b in zip(client.starts, client.starts[1:]))
    assert receipt["coverage"]["AAPL"]["bars"] == 4
    manifest = write_daily_manifest(spec, tmp_path / "stage", receipt)
    assert manifest["accepted_research"] is False
    assert "connection_file" not in manifest["spec"]
    assert (
        verify_daily_manifest(tmp_path / "stage/manifest.json")["status"] == "acquired"
    )
    (tmp_path / "stage/normalized/AAPL.csv").write_text("tampered")
    with pytest.raises(ValueError, match="HASH"):
        verify_daily_manifest(tmp_path / "stage/manifest.json")


def test_missing_stock_is_partial_not_a_smaller_pool(tmp_path, monkeypatch):
    spec, receipt, _, _ = run(tmp_path, monkeypatch, missing=True)
    assert receipt["status"] == "partial"
    assert set(receipt["coverage"]) == {"AAPL", "SPY"}
    assert any(g["product"] == "AAPL" for g in receipt["gaps"])


@pytest.mark.parametrize(
    "budget,code",
    [
        ({"requests": 1, "bytes": 33554432, "seconds": 2400}, "REQUEST_BUDGET"),
        ({"requests": 120, "bytes": 1, "seconds": 2400}, "BYTE_BUDGET"),
        ({"requests": 120, "bytes": 33554432, "seconds": 1}, "TIME_BUDGET"),
    ],
)
def test_budgets_preserve_partial_receipt(tmp_path, monkeypatch, budget, code):
    _, receipt, _, _ = run(tmp_path, monkeypatch, budget=budget)
    assert receipt["status"] == "partial"
    assert code in receipt["issue_codes"]
    assert receipt["retained_payload_bytes"] <= budget["bytes"]


def test_nonfinite_data_is_not_published_as_complete(tmp_path, monkeypatch):
    _, receipt, _, _ = run(tmp_path, monkeypatch, bad=True)
    assert receipt["status"] == "partial"
    assert "INVALID_BARS" in receipt["issue_codes"]


def test_resume_verifies_owned_checkpoint_bytes(tmp_path, monkeypatch):
    spec, receipt, _, _ = run(tmp_path, monkeypatch)
    raw = next((tmp_path / "stage/raw").glob("*.json"))
    raw.write_text("tampered")
    with pytest.raises(ValueError, match="HASH"):
        collect_daily(
            spec,
            tmp_path / "stage",
            session_factory=None,
            clock=Clock(),
            sleep=lambda x: None,
        )


def test_manifest_rejects_traversal(tmp_path, monkeypatch):
    spec, receipt, _, _ = run(tmp_path, monkeypatch)
    manifest = write_daily_manifest(spec, tmp_path / "stage", receipt)
    manifest["files"][0]["path"] = "../outside"
    (tmp_path / "stage/manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="PATH"):
        verify_daily_manifest(tmp_path / "stage/manifest.json")


def test_collection_lock_is_not_removed_by_competing_writer(tmp_path, monkeypatch):
    lock = tmp_path / "stage.collection-lock"
    lock.write_text("other-writer")
    with pytest.raises(ValueError, match="COLLECTION_IN_PROGRESS"):
        run(tmp_path, monkeypatch)
    assert lock.read_text() == "other-writer"


def test_unchanged_resume_does_not_request_again(tmp_path, monkeypatch):
    spec, before, _, clock = run(tmp_path, monkeypatch)

    class Session:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return Client(clock)

        def __exit__(self, *args):
            pass

    after = collect_daily(
        spec,
        tmp_path / "stage",
        session_factory=Session,
        clock=clock,
        sleep=clock.sleep,
    )
    assert after["requests"] == before["requests"]
    assert after["status"] == "acquired"


def test_partial_empty_response_can_resume_without_discarding_good_data(
    tmp_path, monkeypatch
):
    spec, before, _, clock = run(tmp_path, monkeypatch, missing=True)
    assert before["status"] == "partial"

    class Session:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return Client(clock)

        def __exit__(self, *a):
            pass

    after = collect_daily(
        spec,
        tmp_path / "stage",
        session_factory=Session,
        clock=clock,
        sleep=clock.sleep,
    )
    assert after["status"] == "acquired"
    assert after["coverage"]["AAPL"]["bars"] == 4


def test_interrupt_releases_own_lock_and_retains_verified_checkpoint(
    tmp_path, monkeypatch
):
    spec, _, _, clock = run(tmp_path / "fixture", monkeypatch)

    class Interrupted(Client):
        def reqHistoricalData(self, *a, **k):
            raise KeyboardInterrupt

    class Session:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return Interrupted(clock)

        def __exit__(self, *a):
            pass

    with pytest.raises(KeyboardInterrupt):
        collect_daily(
            spec,
            tmp_path / "new",
            session_factory=Session,
            clock=clock,
            sleep=clock.sleep,
        )
    assert not (tmp_path / "new.collection-lock").exists()
    checkpoint = json.loads((tmp_path / "new/checkpoint.json").read_text())
    assert checkpoint["requests"] == 2
    assert checkpoint["files"] == []


def test_serialization_time_is_included_in_budget(tmp_path, monkeypatch):
    from competition_tools.datasets import daily_broker

    spec, _, _, clock = run(tmp_path / "fixture", monkeypatch)
    original = daily_broker._normalized

    def slow(rows):
        clock.sleep(2500)
        return original(rows)

    monkeypatch.setattr(daily_broker, "_normalized", slow)

    class Session:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return Client(clock)

        def __exit__(self, *a):
            pass

    receipt = collect_daily(
        spec, tmp_path / "new", session_factory=Session, clock=clock, sleep=clock.sleep
    )
    assert receipt["status"] == "partial"
    assert receipt["issue_codes"] == ["TIME_BUDGET"]
    assert receipt["retained_payload_bytes"] == 0


def test_generated_receipt_and_manifest_match_schemas(tmp_path, monkeypatch):
    from pathlib import Path
    import jsonschema

    spec, receipt, _, _ = run(tmp_path, monkeypatch)
    manifest = write_daily_manifest(spec, tmp_path / "stage", receipt)
    schema_root = Path(__file__).resolve().parents[3] / "schemas/research"
    for name, value in [
        ("dataset-spec", spec),
        ("dataset-receipt", receipt),
        ("dataset-manifest", manifest),
    ]:
        schema = json.loads((schema_root / f"{name}.v2.schema.json").read_text())
        jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()
        ).validate(value)


def test_calendar_preparation_consumes_time_before_connection(tmp_path, monkeypatch):
    spec, _, _, clock = run(tmp_path / "fixture", monkeypatch)
    from competition_tools.datasets import daily_broker

    original = daily_broker.completed_sessions

    def slow(*args, **kwargs):
        clock.sleep(2500)
        return original(*args, **kwargs)

    monkeypatch.setattr(daily_broker, "completed_sessions", slow)

    def forbidden(*a, **k):
        pytest.fail("Expired budget must not connect")

    receipt = collect_daily(
        spec,
        tmp_path / "new",
        session_factory=forbidden,
        clock=clock,
        sleep=clock.sleep,
    )
    assert receipt["issue_codes"] == ["TIME_BUDGET"]


@pytest.mark.parametrize(
    "delay,seconds,expected", [(25, 20, "partial"), (11, 2400, "acquired")]
)
def test_checkpoint_delay_cannot_bypass_request_deadline_or_spacing(
    tmp_path, monkeypatch, delay, seconds, expected
):
    spec, _, _, _ = run(tmp_path / "fixture", monkeypatch)
    from competition_tools.datasets import daily_broker

    original = daily_broker.write_json
    clock = Clock()
    client = Client(clock)
    delayed = False

    def slow(path, value):
        nonlocal delayed
        if path.name == "checkpoint.json" and value["requests"] and not delayed:
            clock.sleep(delay)
            delayed = True
        original(path, value)

    monkeypatch.setattr(daily_broker, "write_json", slow)

    class Session:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return client

        def __exit__(self, *a):
            pass

    spec = spec | {"budget": spec["budget"] | {"seconds": seconds}}
    receipt = collect_daily(
        spec, tmp_path / "new", session_factory=Session, clock=clock, sleep=clock.sleep
    )
    assert receipt["status"] == expected
    if expected == "partial":
        assert client.starts == []
        assert receipt["issue_codes"] == ["TIME_BUDGET"]
    else:
        assert all(b - a >= 10 for a, b in zip(client.starts, client.starts[1:]))


def test_eleven_contracts_across_annual_windows(tmp_path, monkeypatch):
    spec, _, _, clock = run(tmp_path / "fixture", monkeypatch)
    dates = ["2023-01-03", "2024-01-02", "2025-01-02", "2026-01-02"]
    monkeypatch.setattr(
        "competition_tools.datasets.daily_broker.completed_sessions",
        lambda *a, **k: {
            "sessions": dates,
            "calendar_name": "XNYS",
            "package_version": "synthetic",
            "schedule_sha256": "c" * 64,
            "latest_completed_session": dates[-1],
        },
    )
    products = [f"S{i}" for i in range(10)]
    spec = spec | {
        "products": products,
        "start": "2023-01-01",
        "end": dates[-1],
        "contracts": [
            {
                "product": p,
                "symbol": p,
                "currency": "USD",
                "exchange": "SMART",
                "role": "benchmark" if p == "SPY" else "stock",
            }
            for p in products + ["SPY"]
        ],
    }

    class Annual(Client):
        def qualifyContracts(self, contract):
            self.starts.append(clock())
            contract.conId = (
                100 if contract.symbol == "SPY" else 1 + int(contract.symbol[1:])
            )
            return [contract]

        def reqHistoricalData(self, contract, **kwargs):
            self.starts.append(clock())
            return [
                SimpleNamespace(
                    date=date.fromisoformat(d),
                    open=100,
                    high=100,
                    low=100,
                    close=100,
                    volume=5,
                )
                for d in dates
            ]

    client = Annual(clock)

    class Session:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return client

        def __exit__(self, *a):
            pass

    receipt = collect_daily(
        spec, tmp_path / "new", session_factory=Session, clock=clock, sleep=clock.sleep
    )
    assert receipt["status"] == "acquired"
    assert receipt["requests"] == 55
    assert len(receipt["coverage"]) == 11
    assert all(c["bars"] == 4 for c in receipt["coverage"].values())
    assert all(b - a >= 10 for a, b in zip(client.starts, client.starts[1:]))


@pytest.mark.parametrize(
    "upper,zone,expected",
    [
        ("2024-03-08", "America/New_York", "20240309-05:00:00"),
        ("2024-03-11", "America/New_York", "20240312-04:00:00"),
        ("2024-07-05", "Asia/Hong_Kong", "20240705-16:00:00"),
    ],
)
def test_broker_end_time_is_explicit_utc_after_local_session(upper, zone, expected):
    from competition_tools.datasets.daily_broker import request_end

    assert request_end(upper, zone) == expected


@pytest.mark.parametrize(
    "volume,flat,complete", [(0, True, True), (1, True, False), (0, False, False)]
)
def test_closed_session_placeholders_are_audited_not_used_as_trading_days(
    tmp_path, monkeypatch, volume, flat, complete
):
    spec, _, _, clock = run(tmp_path / "fixture", monkeypatch)

    class Closed(Client):
        def reqHistoricalData(self, contract, **kwargs):
            rows = super().reqHistoricalData(contract, **kwargs)
            rows.append(
                SimpleNamespace(
                    date=date(2024, 7, 4),
                    open=100,
                    high=100 if flat else 101,
                    low=100,
                    close=100,
                    volume=volume,
                )
            )
            return sorted(rows, key=lambda b: b.date)

    class Session:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return Closed(clock)

        def __exit__(self, *a):
            pass

    receipt = collect_daily(
        spec, tmp_path / "new", session_factory=Session, clock=clock, sleep=clock.sleep
    )
    if complete:
        assert receipt["status"] == "acquired"
        assert receipt["coverage"]["AAPL"]["bars"] == 4
        assert receipt["excluded_non_session_bars"] == [
            {
                "product": p,
                "date": "2024-07-04",
                "reason": "CLOSED_SESSION_ZERO_VOLUME_FLAT",
            }
            for p in ["AAPL", "SPY"]
        ]
        raw = json.loads(next((tmp_path / "new/raw").glob("AAPL-*.json")).read_text())
        assert any(row[0] == "2024-07-04" for row in raw)
        assert "2024-07-04" not in (tmp_path / "new/normalized/AAPL.csv").read_text()
    else:
        assert receipt["status"] == "partial"
        assert receipt["issue_codes"] == ["NONSESSION_BAR"]
