"""Binance public spot daily archives; never event-book inputs."""

import csv
import hashlib
import io
import re
import stat
import zipfile
from datetime import datetime, timezone

from .quality import validate_bars


def archive_url(product: str, month: str) -> str:
    if not re.fullmatch(r"[A-Z0-9]+USDT", product) or not re.fullmatch(
        r"\d{4}-(0[1-9]|1[0-2])", month
    ):
        raise ValueError("INVALID_ARCHIVE_IDENTITY")
    return f"https://data.binance.vision/data/spot/monthly/klines/{product}/1d/{product}-1d-{month}.zip"


def normalize_archive(
    payload: bytes, checksum: str, product: str, month: str
) -> list[list[str]]:
    archive_url(product, month)
    name = f"{product}-1d-{month}"
    fields = checksum.strip().split()
    if (
        len(fields) != 2
        or fields[1].lstrip("*") != name + ".zip"
        or fields[0] != hashlib.sha256(payload).hexdigest()
    ):
        raise ValueError("ARCHIVE_CHECKSUM_MISMATCH")
    if len(payload) > 25 * 1024 * 1024:
        raise ValueError("ARCHIVE_TOO_LARGE")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = archive.infolist()
        if len(members) != 1 or members[0].filename != name + ".csv":
            raise ValueError("UNEXPECTED_ARCHIVE_MEMBER")
        member = members[0]
        if (
            stat.S_ISLNK(member.external_attr >> 16)
            or member.file_size > 100 * 1024 * 1024
        ):
            raise ValueError("UNSAFE_ARCHIVE_MEMBER")
        with archive.open(member) as stream:
            body = stream.read(100 * 1024 * 1024 + 1)
        if len(body) > 100 * 1024 * 1024:
            raise ValueError("ARCHIVE_TOO_LARGE")
    rows = []
    divisor = 1_000_000 if month >= "2025-01" else 1_000
    for row in csv.reader(io.StringIO(body.decode("utf-8-sig"))):
        if len(row) != 12:
            raise ValueError("INVALID_KLINE_COLUMNS")
        timestamp = int(row[0])
        instant = datetime.fromtimestamp(timestamp / divisor, timezone.utc)
        if (
            instant.strftime("%Y-%m") != month
            or instant.hour
            or instant.minute
            or instant.second
            or instant.microsecond
        ):
            raise ValueError("INVALID_KLINE_TIMESTAMP")
        rows.append([instant.date().isoformat(), *row[1:6]])
    validate_bars(rows)
    if not rows:
        raise ValueError("EMPTY_ARCHIVE")
    return rows
