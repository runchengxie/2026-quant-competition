"""Real archive normalization through a deterministic network boundary."""

import hashlib
import io
import json
import zipfile

import pytest

from competition_tools.datasets.acquisition import acquire
from competition_tools.datasets.storage import write_manifest, verify_manifest
from competition_tools.datasets.transport import Transport, DatasetBlocked


def test_resume_checksum_interruption_and_inspect_partial(tmp_path, monkeypatch):
    spec = {
        "schema": "competition.dataset_spec.v1",
        "dataset_id": "fixture",
        "version": "v1",
        "source": "binance_spot",
        "market": "crypto",
        "products": ["BTCUSDT"],
        "quote_currency": "USDT",
        "start": "2024-01-01",
        "end": "2024-01-31",
        "timezone": "UTC",
        "calendar": "365",
        "price_basis": "raw",
        "universe_status": "fixed_current",
        "budget": {"requests": 20, "bytes": 10000, "seconds": 600},
    }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "BTCUSDT-1d-2024-01.csv", "1704067200000,1,2,0.5,1,1,0,0,0,0,0,0\n"
        )
    payload = stream.getvalue()
    calls = []
    interrupted = [True]

    def fetch(self, url, path):
        calls.append(url)
        if url.endswith("CHECKSUM") and interrupted[0]:
            raise DatasetBlocked("RETRIES_EXHAUSTED")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            (hashlib.sha256(payload).hexdigest() + "  BTCUSDT-1d-2024-01.zip").encode()
            if url.endswith("CHECKSUM")
            else payload
        )
        return {}

    monkeypatch.setattr(Transport, "fetch", fetch)
    assert acquire(spec, tmp_path / "staging")["status"] == "partial"
    interrupted[0] = False
    result = acquire(spec, tmp_path / "staging")
    assert result["coverage"]["BTCUSDT"]["rows"] == 1
    assert sum(not u.endswith("CHECKSUM") for u in calls) == 1
    assert result["status"] == "partial"  # A one-day file is not a complete month.
    write_manifest(spec, tmp_path / "staging")
    assert verify_manifest(tmp_path / "staging/manifest.json")["status"] == "partial"
    (tmp_path / "staging/raw/BTCUSDT/BTCUSDT-1d-2024-01.zip").write_bytes(b"bad")
    with pytest.raises(ValueError, match="HASH"):
        acquire(spec, tmp_path / "staging")


def test_every_dataset_contract_has_a_schema():
    from pathlib import Path
    from jsonschema import Draft202012Validator

    root = Path(__file__).resolve().parents[3]
    for name in (
        "dataset-spec",
        "dataset-manifest",
        "dataset-receipt",
        "coverage-report",
    ):
        path = root / "schemas/research" / f"{name}.v1.schema.json"
        Draft202012Validator.check_schema(json.loads(path.read_text()))


def test_licensed_import_charges_total_input_bytes(tmp_path):
    from competition_tools.datasets.acquisition import import_licensed

    source = tmp_path / "source"
    source.mkdir()
    body = "date,open,high,low,close,volume\n2024-01-01,1,2,0.5,1,1\n"
    for product in ("A", "B"):
        (source / f"{product}.csv").write_text(body)
    staging = tmp_path / "staging"
    staging.mkdir()
    with pytest.raises(DatasetBlocked, match="BYTE_BUDGET"):
        import_licensed(
            {
                "input_directory": str(source),
                "universe_status": "fixed_current",
                "market": "US",
                "calendar": "XNYS",
                "source": "licensed_import",
                "products": ["A", "B"],
                "start": "2024-01-01",
                "end": "2024-12-31",
                "budget": {
                    "bytes": (source / "A.csv").stat().st_size + 1,
                    "seconds": 600,
                },
            },
            staging,
        )


def licensed_fixture(tmp_path, *, status="fixed_current", market="US", calendar="XNYS"):
    source = tmp_path / "source"
    source.mkdir()
    (source / "SPY.csv").write_text(
        "date,open,high,low,close,volume\n2024-06-03,1,2,0.5,1,1\n"
    )
    staging = tmp_path / "staging"
    staging.mkdir()
    membership = tmp_path / "membership.csv"
    spec = {
        "source": "licensed_import",
        "market": market,
        "calendar": calendar,
        "products": ["SPY"],
        "input_directory": str(source),
        "membership_file": str(membership),
        "universe_status": status,
        "start": "2024-01-01",
        "end": "2024-12-31",
        "budget": {"bytes": 100000, "seconds": 600},
    }
    return spec, staging, membership


@pytest.mark.parametrize(
    "membership_rows",
    [
        "",
        "other,QQQ,2024-01-01,2024-12-31,2023-12-31\n",
        "spy,SPY,2020-01-01,2020-12-31,2019-12-31\n",
    ],
)
def test_pit_requires_relevant_nonempty_membership(tmp_path, membership_rows):
    from competition_tools.datasets.acquisition import import_licensed

    spec, staging, membership = licensed_fixture(tmp_path, status="point_in_time")
    membership.write_text(
        "stable_id,symbol,valid_from,valid_to,available_at\n" + membership_rows
    )
    with pytest.raises(DatasetBlocked, match="PIT_MEMBERSHIP"):
        import_licensed(spec, staging)


def test_one_day_is_not_complete_requested_equity_year(tmp_path):
    from competition_tools.datasets.acquisition import import_licensed

    spec, staging, _ = licensed_fixture(tmp_path)
    result = import_licensed(spec, staging)
    assert result["status"] == "partial"
    assert result["gaps"]
    assert result["coverage"]["SPY"]["rows"] == 1


def test_complete_continuous_calendar_can_be_acquired(tmp_path):
    from competition_tools.datasets.acquisition import import_licensed

    spec, staging, _ = licensed_fixture(tmp_path, market="crypto", calendar="365")
    spec.update(start="2024-06-03", end="2024-06-04")
    (tmp_path / "source/SPY.csv").write_text(
        "date,open,high,low,close,volume\n2024-06-03,1,2,0.5,1,1\n2024-06-04,1,2,0.5,1,1\n"
    )
    assert import_licensed(spec, staging)["status"] == "acquired"


def test_licensed_input_revision_requires_new_version(tmp_path):
    from competition_tools.datasets.acquisition import import_licensed

    spec, staging, _ = licensed_fixture(tmp_path)
    import_licensed(spec, staging)
    original = (staging / "normalized/SPY.csv").read_bytes()
    path = tmp_path / "source/SPY.csv"
    path.write_text(path.read_text().replace(",1,1\n", ",1.2,1\n"))
    with pytest.raises(ValueError, match="REVISION"):
        import_licensed(spec, staging)
    assert (staging / "normalized/SPY.csv").read_bytes() == original


def test_interrupted_import_retains_input_identity(tmp_path, monkeypatch):
    from competition_tools.datasets import acquisition

    spec, staging, _ = licensed_fixture(tmp_path)
    write_json = acquisition.write_json

    def fail_receipt(path, value):
        if path.name == "receipt.json":
            raise OSError("simulated receipt interruption")
        write_json(path, value)

    with monkeypatch.context() as context:
        context.setattr(acquisition, "write_json", fail_receipt)
        with pytest.raises(OSError):
            acquisition.import_licensed(spec, staging)
    source = tmp_path / "source/SPY.csv"
    source.write_text(source.read_text().replace(",1,1\n", ",1.2,1\n"))
    with pytest.raises(ValueError, match="REVISION"):
        acquisition.import_licensed(spec, staging)
