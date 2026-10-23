"""Daily archives must not silently accept a different date or unsafe payload."""

import hashlib
import io
import zipfile
from datetime import datetime, timezone

import pytest


def sample(day="2025-01-01", *, body=None, member=None):
    name = f"BTCUSDT-1d-{day}"
    timestamp = int(
        datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()
    )
    timestamp *= 1_000_000 if day >= "2025-01-01" else 1_000
    line = body or f"{timestamp},1,2,0.5,1.5,10,0,15,4,1,2,0\n"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr(member or name + ".csv", line)
    payload = stream.getvalue()
    return payload, f"{hashlib.sha256(payload).hexdigest()}  {name}.zip"


@pytest.mark.parametrize("day", ["2024-01-01", "2025-01-01"])
def test_daily_units_and_exact_date(day):
    from competition_tools.datasets.binance_daily import normalize_daily_archive

    assert normalize_daily_archive(*sample(day), "BTCUSDT", day) == [
        [day, "1", "2", "0.5", "1.5", "10"]
    ]


@pytest.mark.parametrize(
    "kind", ["date", "duplicate", "nonfinite", "path", "size", "checksum", "product"]
)
def test_daily_invalid_payloads(kind):
    from competition_tools.datasets.binance_daily import normalize_daily_archive

    args = list(sample()) + ["BTCUSDT", "2025-01-01"]
    if kind == "date":
        args[3] = "2025-01-02"
    elif kind == "duplicate":
        args[:2] = sample(body="1735689600000000,1,2,.5,1,1,0,0,0,0,0,0\n" * 2)
    elif kind == "nonfinite":
        args[:2] = sample(body="1735689600000000,1,2,.5,nan,1,0,0,0,0,0,0\n")
    elif kind == "path":
        args[:2] = sample(member="../bad.csv")
    elif kind == "size":
        args[:2] = sample(body="x" * (4 * 1024 * 1024 + 1))
    elif kind == "checksum":
        args[1] = "0" * 64 + " BTCUSDT-1d-2025-01-01.zip"
    else:
        args[2] = "UNKNOWNUSDT"
    with pytest.raises(ValueError):
        normalize_daily_archive(*args)
