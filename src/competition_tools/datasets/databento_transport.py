"""Single-host, no-retry transport and conservative fixed-record billing bound."""

import base64
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .databento_spec import BUDGET, safe_path

METHODS = {
    "metadata.get_cost",
    "metadata.get_billable_size",
    "metadata.list_unit_prices",
    "metadata.get_record_count",
    "symbology.resolve",
}
BILLING_SOURCES = [
    "https://databento.com/docs/api-historical?lang=http",
    "https://databento.com/docs/api-historical/metadata?lang=python",
    "https://github.com/databento/dbn/blob/main/rust/dbn/src/record.rs",
]


def decimal_value(value: object) -> Decimal:
    try:
        if isinstance(value, bool):
            raise ValueError
        result = Decimal(str(value))
        if not result.is_finite() or result < 0:
            raise ValueError
        return result
    except (ValueError, InvalidOperation):
        raise ValueError("INVALID_COST") from None


def validate_cost_bound(
    quote: object, billing_evidence: dict, maximum_usd: Decimal
) -> dict:
    e = billing_evidence
    quoted, price = decimal_value(quote), decimal_value(e.get("unit_price_usd_per_gb"))
    if maximum_usd != Decimal("0.10") or quoted > maximum_usd or price <= 0:
        raise ValueError("COST_BUDGET")
    if (
        type(e.get("record_count")) is not int
        or not 0 < e["record_count"] < 4000
        or type(e.get("billable_bytes")) is not int
        or not 0 < e["billable_bytes"] <= 4000 * 56
        or not re.fullmatch("[0-9a-f]{64}", e.get("request_sha256", ""))
        or e["request_sha256"] != e.get("quote_request_sha256")
    ):
        raise ValueError("BILLING_BOUND_UNVERIFIED")
    # Server-enforced record cap, 56-byte OhlcvMsg; reserve an extra 1 MiB.
    # Decimal GB is conservative even if the rate uses binary GiB.
    bound_bytes = 4000 * 56 + 1048576
    bound = Decimal(bound_bytes) * price / Decimal(1000000000)
    if bound > maximum_usd or quoted > bound:
        raise ValueError("COST_BUDGET")
    return {
        "quoted_cost_usd": str(quoted),
        "unit_price_usd_per_gb": str(price),
        "conservative_cost_usd": str(bound),
        "bound_bytes": bound_bytes,
        "record_limit": 4000,
        "record_bytes": 56,
        "sources": BILLING_SOURCES,
        "request_sha256": e["request_sha256"],
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class DatabentoTransport:
    def __init__(
        self,
        credential_file: Path,
        budget: dict,
        ledger: Path,
        *,
        opener=None,
        monotonic=None,
    ):
        self.clock = monotonic or time.monotonic
        self.started = self.clock()
        if budget != BUDGET or any(
            type(budget[k]) is not type(v) for k, v in BUDGET.items()
        ):
            raise ValueError("INVALID_BUDGET")
        self.budget = dict(budget)
        self.ledger = safe_path(ledger)
        if self.ledger.exists():
            raise ValueError("REQUEST_LEDGER_EXISTS")
        self.metadata_requests = self.download_requests = self.bytes = 0
        self.key = self.auth = None
        self.credential_file = safe_path(credential_file)
        self.opener = opener or urllib.request.build_opener(NoRedirect())

    def _credentials(self):
        if self.key is not None:
            return
        values = []
        for line in self.credential_file.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            match = re.fullmatch(r"\s*DATABENTO_API_KEY\s*=\s*(.*?)\s*", line)
            if not match:
                raise ValueError("INVALID_CREDENTIAL_FILE")
            value = match[1]
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if not value or any(ord(c) < 33 or ord(c) > 126 for c in value):
                raise ValueError("INVALID_CREDENTIAL_FILE")
            values.append(value)
        if len(values) != 1:
            raise ValueError("INVALID_CREDENTIAL_FILE")
        self.key = values[0]
        self.auth = "Basic " + base64.b64encode((self.key + ":").encode()).decode()

    def check_time(self):
        remaining = self.budget["seconds"] - (self.clock() - self.started)
        if remaining <= 0:
            raise ValueError("TIME_BUDGET")
        return remaining

    def spent(self):
        return {
            "metadata_requests": self.metadata_requests,
            "download_requests": self.download_requests,
            "bytes": self.bytes,
            "seconds": self.clock() - self.started,
        }

    def _log(self, value):
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, allow_nan=False) + "\n")

    def _fetch(self, method, parameters):
        download = method == "timeseries.get_range"
        if method not in METHODS and not download:
            raise ValueError("ENDPOINT_REJECTED")
        remaining = self.check_time()
        counter = "download_requests" if download else "metadata_requests"
        if getattr(self, counter) >= self.budget[counter]:
            raise ValueError("REQUEST_BUDGET")
        self._credentials()
        setattr(self, counter, getattr(self, counter) + 1)
        self._log(
            {"method": method, "state": "started", "attempt": getattr(self, counter)}
        )
        payload = urllib.parse.urlencode(parameters).encode()
        url = "https://hist.databento.com/v0/" + method
        # symbology and timeseries use form-encoded POST; metadata uses GET.
        post = download or method == "symbology.resolve"
        request = urllib.request.Request(
            url if post else url + "?" + payload.decode(),
            data=payload if post else None,
            headers={
                "Authorization": self.auth,
                "Accept-Encoding": "identity",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        raw = bytearray()
        try:
            with self.opener.open(request, timeout=min(25, remaining)) as response:
                if response.status != 200:
                    raise ValueError("PROVIDER_STATUS_REJECTED")
                if response.headers.get("Content-Encoding", "identity") not in (
                    "identity",
                    "",
                ):
                    raise ValueError("ENCODING_REJECTED")
                while True:
                    self.check_time()
                    chunk = response.read(
                        min(65536, self.budget["bytes"] - self.bytes + 1)
                    )
                    if not chunk:
                        break
                    self.bytes += len(chunk)
                    if self.bytes > self.budget["bytes"]:
                        raise ValueError("BYTE_BUDGET")
                    raw.extend(chunk)
            self.check_time()
            text = raw.decode("utf-8-sig")
            # Match literal and JSON-escaped secrets; no raw error data is logged.
            if (
                self.key in text
                or self.auth in text
                or self.key in text.replace("\\/", "/")
            ):
                raise ValueError("SECRET_ECHO_REJECTED")
            self._log({"method": method, "state": "completed", "bytes": len(raw)})
            return text
        except urllib.error.HTTPError as exc:
            # Count error bytes without keeping the body or its text.
            try:
                while self.bytes <= self.budget["bytes"]:
                    self.check_time()
                    block = exc.read(min(65536, self.budget["bytes"] - self.bytes + 1))
                    if not block:
                        break
                    self.bytes += len(block)
            except Exception:
                pass
            finally:
                exc.close()
            self._log({"method": method, "state": "http_error", "status": exc.code})
            raise ValueError(f"PROVIDER_HTTP_{exc.code}") from None
        except ValueError:
            self._log({"method": method, "state": "rejected"})
            raise
        except Exception:
            self._log({"method": method, "state": "connection_failed"})
            raise ValueError("PROVIDER_CONNECTION_FAILED") from None

    def get_metadata(self, method: str, parameters: dict) -> object:
        if method not in METHODS:
            raise ValueError("ENDPOINT_REJECTED")
        text = self._fetch(method, parameters)
        try:
            value = json.loads(
                text,
                parse_float=Decimal,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
            )
            if self.key in json.dumps(value, default=str):
                raise ValueError
            return value
        except (ValueError, TypeError):
            raise ValueError("INVALID_PROVIDER_JSON") from None

    def download_csv(self, parameters: dict, destination: Path) -> None:
        destination = safe_path(destination)
        if destination.exists():
            raise ValueError("RAW_FILE_EXISTS")
        text = self._fetch(
            "timeseries.get_range",
            {
                **parameters,
                "encoding": "csv",
                "pretty_px": "true",
                "pretty_ts": "true",
                "map_symbols": "true",
                "compression": "none",
            },
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8", newline="") as stream:
            stream.write(text)
