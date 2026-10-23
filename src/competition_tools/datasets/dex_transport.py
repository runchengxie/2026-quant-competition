"""Bounded, single-host Pro REST transport. Never retain response error bodies."""

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from .dex_credentials import load_key
from .dex_spec import CAPS, address_valid, safe_path, utc_hour
from .transport import DatasetBlocked, NoRedirect


def resource_url(endpoint, network=None, address=None, query=None):
    if endpoint not in {"usage", "networks", "token", "token_ohlcv", "pool"}:
        raise ValueError("ENDPOINT_NOT_ALLOWED")
    query = {} if query is None else query
    if not isinstance(query, dict):
        raise ValueError("QUERY_NOT_ALLOWED")
    if endpoint in {"usage", "networks"}:
        if network is not None or address is not None or query:
            raise ValueError("RESOURCE_NOT_ALLOWED")
        path = "/" + endpoint
    else:
        if not address_valid(network, address):
            raise ValueError("RESOURCE_NOT_ALLOWED")
        kind = "pools" if endpoint == "pool" else "tokens"
        path = f"/networks/{network}/{kind}/{address}"
        if endpoint == "token_ohlcv":
            if set(query) != {"start", "end", "interval", "limit"}:
                raise ValueError("QUERY_NOT_ALLOWED")
            start, end = utc_hour(query["start"]), utc_hour(query["end"])
            if (
                not 0 < (end - start).total_seconds() <= 720 * 3600
                or query["interval"] != "1h"
                or type(query["limit"]) is not int
                or query["limit"] != 1000
            ):
                raise ValueError("QUERY_NOT_ALLOWED")
            path += "/ohlcv"
        elif query:
            raise ValueError("QUERY_NOT_ALLOWED")
    return (
        "https://api-pro.dexpaprika.com"
        + path
        + ("?" + urlencode(sorted(query.items())) if query else "")
    )


class DexTransport:
    def __init__(
        self,
        budget: dict,
        credential_file: Path,
        ledger: Path,
        *,
        opener=None,
        clock=None,
        sleep=None,
        utc_now=None,
    ):
        if set(budget) != set(CAPS) or any(
            type(budget[k]) is not int or not 0 < budget[k] <= cap
            for k, cap in CAPS.items()
        ):
            raise ValueError("INVALID_DEX_BUDGET")
        self.budget = dict(budget)
        self.ledger = safe_path(ledger)
        if self.ledger.exists():
            raise ValueError("LEDGER_EXISTS")
        self.credential_file = credential_file
        self.utc_now = utc_now or (lambda: datetime.now(timezone.utc))
        self.clock = clock or time.monotonic
        self.sleep = sleep or time.sleep
        self.started = self.clock()
        self.last_start = None
        self.requests = 0
        self.bytes = 0
        self.credit_state = None
        self.resource_attempts = {}
        self.opener = opener or build_opener(NoRedirect()).open

    def remaining_time(self):
        return self.budget["seconds"] - (self.clock() - self.started)

    def _wait(self, delay):
        if delay >= self.remaining_time():
            raise DatasetBlocked("TIME_BUDGET")
        if delay > 0:
            self.sleep(delay)

    def _start(self):
        if self.requests >= self.budget["requests"]:
            raise DatasetBlocked("REQUEST_BUDGET")
        if self.bytes >= self.budget["bytes"]:
            raise DatasetBlocked("BYTE_BUDGET")
        if self.last_start is not None:
            self._wait(
                max(
                    0,
                    60 / self.budget["requests_per_minute"]
                    - (self.clock() - self.last_start),
                )
            )
        if self.remaining_time() <= 0:
            raise DatasetBlocked("TIME_BUDGET")
        self.last_start = self.clock()
        self.requests += 1

    def _read(self, stream):
        body = bytearray()
        while True:
            if self.remaining_time() <= 0:
                raise DatasetBlocked("TIME_BUDGET")
            chunk = stream.read(min(65536, self.budget["bytes"] - self.bytes + 1))
            if not chunk:
                return bytes(body)
            self.bytes += len(chunk)
            if self.bytes > self.budget["bytes"]:
                raise DatasetBlocked("BYTE_BUDGET")
            body.extend(chunk)

    def _record(self, record):
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, allow_nan=False) + "\n")
            stream.flush()

    def get_json(self, endpoint, *, network=None, address=None, query=None):
        url = resource_url(endpoint, network, address, query)
        key = load_key(self.credential_file)
        for attempt in range(
            0 if endpoint == "usage" else self.resource_attempts.get(url, 0), 2
        ):
            self._start()
            if endpoint != "usage":
                self.resource_attempts[url] = attempt + 1
            record = {
                "endpoint": endpoint,
                "resource": url,
                "attempt": attempt + 1,
                "request_number": self.requests,
                "status": "interrupted",
            }
            before = self.bytes
            # Write a start before I/O. An unclosed attempt blocks automatic resume.
            self._record(record)
            retry = 1
            try:
                request = Request(
                    url,
                    headers={
                        "Authorization": key,
                        "Accept": "application/json",
                        "Accept-Encoding": "identity",
                    },
                )
                with self.opener(
                    request, timeout=min(30, self.remaining_time())
                ) as response:
                    if (
                        response.headers.get("Content-Encoding", "identity")
                        != "identity"
                    ):
                        raise DatasetBlocked("ENCODING_NOT_ALLOWED")
                    body = self._read(response)
                    if key.encode() in body:
                        raise DatasetBlocked("RESPONSE_SECRET_ECHO")
                    if "application/json" not in response.headers.get(
                        "Content-Type", ""
                    ):
                        raise DatasetBlocked("NON_JSON_RESPONSE")
                    try:
                        value = json.loads(
                            body,
                            parse_constant=lambda _: (_ for _ in ()).throw(
                                ValueError()
                            ),
                        )
                        # Also reject floating-point overflow (e.g. 1e999).
                        decoded = json.dumps(value, allow_nan=False, ensure_ascii=False)
                    except (ValueError, UnicodeError):
                        raise DatasetBlocked("INVALID_JSON_RESPONSE") from None
                    if not isinstance(value, (dict, list)):
                        raise DatasetBlocked("INVALID_JSON_RESPONSE")
                    if key in decoded:
                        raise DatasetBlocked("RESPONSE_SECRET_ECHO")
                    record["status"] = "ok"
                    return value
            except HTTPError as error:
                record["status"] = f"HTTP_{error.code}"
                try:
                    self._read(error)
                except (URLError, OSError, TimeoutError):
                    pass  # Error-body transport details are untrusted and never surfaced.
                finally:
                    error.close()
                if error.code not in {429, 500, 502, 503, 504}:
                    raise DatasetBlocked(f"HTTP_{error.code}") from None
                try:
                    delay = float(error.headers.get("Retry-After", "1"))
                    retry = min(60, max(0, delay)) if math.isfinite(delay) else 1
                except (TypeError, ValueError):
                    retry = 1
            except (URLError, OSError, TimeoutError):
                record["status"] = "NETWORK_ERROR"
            except DatasetBlocked as error:
                record["status"] = str(error)
                raise
            finally:
                record.update(bytes=self.bytes - before, total_bytes=self.bytes)
                self._record(record)
            if attempt == 0:
                self._wait(retry)
        raise DatasetBlocked("RETRIES_EXHAUSTED")
