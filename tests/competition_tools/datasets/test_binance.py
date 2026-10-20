"""Archive checks use real ZIP bytes and documented timestamp units."""

import hashlib
import io
import zipfile

import pytest

from competition_tools.datasets.binance import normalize_archive, archive_url


def archive(name, body):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr(name, body)
    return stream.getvalue()


@pytest.mark.parametrize(
    "month,timestamp", [("2024-01", 1704067200000), ("2025-01", 1735689600000000)]
)
def test_documented_spot_units(month, timestamp):
    name = f"BTCUSDT-1d-{month}"
    payload = archive(name + ".csv", f"{timestamp},1,2,0.5,1.5,10,0,15,4,1,2,0\n")
    checksum = f"{hashlib.sha256(payload).hexdigest()}  {name}.zip"
    rows = normalize_archive(payload, checksum, "BTCUSDT", month)
    assert rows == [[month + "-01", "1", "2", "0.5", "1.5", "10"]]


def test_archive_rejects_traversal_and_wrong_checksum():
    payload = archive("../evil.csv", "0,1,2,0,1,1,0,0,0,0,0,0\n")
    checksum = f"{hashlib.sha256(payload).hexdigest()}  BTCUSDT-1d-2024-01.zip"
    with pytest.raises(ValueError):
        normalize_archive(payload, checksum, "BTCUSDT", "2024-01")
    with pytest.raises(ValueError):
        normalize_archive(payload, "0" * 64 + " wrong.zip", "BTCUSDT", "2024-01")


def test_url_cannot_escape_product_path():
    with pytest.raises(ValueError):
        archive_url("../BTCUSDT", "2024-01")
