"""Strict single-day Binance spot archives, separate from monthly imports."""

import csv
import hashlib
import io
import stat
import zipfile
from datetime import date, datetime, timezone

from .quality import validate_bars

PRODUCTS = frozenset({"BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LINKUSDT"})
MAX_EXPANDED = 4 * 1024 * 1024


def daily_archive_url(product: str, day: str) -> str:
    if product not in PRODUCTS or date.fromisoformat(day).isoformat() != day:
        raise ValueError("INVALID_DAILY_ARCHIVE_IDENTITY")
    return f"https://data.binance.vision/data/spot/daily/klines/{product}/1d/{product}-1d-{day}.zip"


def normalize_daily_archive(payload: bytes, checksum: str, product: str, day: str) -> list[list[str]]:
    daily_archive_url(product, day)
    name = f"{product}-1d-{day}"
    fields = checksum.strip().split()
    if len(fields) != 2 or fields[1].lstrip("*") != name + ".zip" or fields[0] != hashlib.sha256(payload).hexdigest():
        raise ValueError("DAILY_CHECKSUM_MISMATCH")
    if len(payload) > MAX_EXPANDED:
        raise ValueError("DAILY_ARCHIVE_TOO_LARGE")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = archive.infolist()
            if len(members) != 1 or members[0].filename != name + ".csv":
                raise ValueError("UNEXPECTED_DAILY_MEMBER")
            member = members[0]
            if member.file_size > MAX_EXPANDED or stat.S_ISLNK(member.external_attr >> 16) or member.flag_bits & 1:
                raise ValueError("UNSAFE_DAILY_MEMBER")
            with archive.open(member) as stream:
                body = stream.read(MAX_EXPANDED + 1)
            if len(body) > MAX_EXPANDED:
                raise ValueError("DAILY_ARCHIVE_TOO_LARGE")
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise ValueError("INVALID_DAILY_ZIP") from exc
    rows = list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))
    if len(rows) != 1 or len(rows[0]) != 12:
        raise ValueError("EXPECTED_ONE_DAILY_BAR")
    row = rows[0]
    divisor = 1_000_000 if day >= "2025-01-01" else 1_000
    expected = int(datetime.combine(date.fromisoformat(day), datetime.min.time(), timezone.utc).timestamp()) * divisor
    if int(row[0]) != expected:
        raise ValueError("WRONG_DAILY_TIMESTAMP")
    normalized = [[day, *row[1:6]]]
    validate_bars(normalized)
    return normalized
