"""Explicit public archive transport with charged retries and bounded reads."""

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class DatasetBlocked(ValueError):
    """A bounded acquisition cannot proceed; retain its checkpoints."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Transport:
    def __init__(self, budget: dict, ledger: Path, *, opener=None):
        self.budget = budget
        self.ledger = ledger
        self.requests = 0
        self.bytes = 0
        self.started = time.monotonic()
        self.opener = opener or build_opener(NoRedirect()).open

    def checkpoint(self):
        if time.monotonic() - self.started >= self.budget["seconds"]:
            raise DatasetBlocked("TIME_BUDGET")
        if self.requests >= self.budget["requests"]:
            raise DatasetBlocked("REQUEST_BUDGET")
        if self.bytes >= self.budget["bytes"]:
            raise DatasetBlocked("BYTE_BUDGET")

    def fetch(self, url: str, destination: Path) -> dict:
        parsed = urlsplit(url)
        pattern = r"/data/spot/monthly/klines/([A-Z0-9]+USDT)/1d/\1-1d-\d{4}-\d{2}\.zip(?:\.CHECKSUM)?"
        if (
            parsed.scheme != "https"
            or parsed.netloc != "data.binance.vision"
            or parsed.query
            or parsed.fragment
            or not re.fullmatch(pattern, parsed.path)
        ):
            raise ValueError("URL_NOT_ALLOWED")
        if destination.exists():
            raise FileExistsError("RAW_FILE_EXISTS")
        destination.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            self.checkpoint()
            self.requests += 1
            record = {"url": url, "attempt": attempt + 1}
            retry = 0
            try:
                request = Request(
                    url, headers={"User-Agent": "competition-offline-research/1"}
                )
                remaining = self.budget["seconds"] - (time.monotonic() - self.started)
                with self.opener(
                    request, timeout=min(30, max(0.1, remaining))
                ) as response:
                    body = bytearray()
                    while True:
                        if time.monotonic() - self.started >= self.budget["seconds"]:
                            raise DatasetBlocked("TIME_BUDGET")
                        chunk = response.read(
                            min(65536, self.budget["bytes"] - self.bytes + 1)
                        )
                        if not chunk:
                            break
                        self.bytes += len(chunk)
                        if self.bytes > self.budget["bytes"]:
                            raise DatasetBlocked("BYTE_BUDGET")
                        body.extend(chunk)
                        if len(body) > 25 * 1024 * 1024:
                            raise DatasetBlocked("ARCHIVE_BYTE_LIMIT")
                if not body:
                    raise DatasetBlocked("EMPTY_RESPONSE")
                with destination.open("xb") as stream:
                    stream.write(body)
                record.update(
                    status="downloaded",
                    bytes=len(body),
                    sha256=hashlib.sha256(body).hexdigest(),
                )
                return record
            except HTTPError as error:
                record["status"] = f"HTTP_{error.code}"
                if error.code == 404:
                    raise DatasetBlocked("ARCHIVE_NOT_AVAILABLE") from None
                if error.code not in {429, 500, 502, 503, 504}:
                    raise DatasetBlocked(f"HTTP_{error.code}") from None
                try:
                    retry = min(
                        60, max(0, float(error.headers.get("Retry-After", "1")))
                    )
                except (TypeError, ValueError):
                    retry = 1
            except (URLError, OSError, TimeoutError):
                record["status"] = "NETWORK_ERROR"
                retry = 1
            finally:
                self.ledger.parent.mkdir(parents=True, exist_ok=True)
                with self.ledger.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(record) + "\n")
            if time.monotonic() - self.started + retry >= self.budget["seconds"]:
                raise DatasetBlocked("TIME_BUDGET")
            time.sleep(retry)
        raise DatasetBlocked("RETRIES_EXHAUSTED")
