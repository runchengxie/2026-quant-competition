"""Small HTTPS/JSON client for provider-confirmed Cryptoracle endpoints."""

from dataclasses import dataclass, field
from http.client import HTTPException
import json
import math
import os
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


_DEFAULT_BASE_URL = "https://service.cryptoracle.network/openapi"


class CryptoracleConfigurationError(ValueError):
    """Raised for missing credentials or an unsafe request configuration."""


class CryptoracleAPIError(RuntimeError):
    """Provider failure with safe diagnostics, without headers or response bodies."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        business_code: int | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.business_code = business_code


@dataclass(frozen=True, slots=True)
class CryptoracleSettings:
    base_url: str = _DEFAULT_BASE_URL
    api_key: str = field(default="", repr=False)
    backup_api_key: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        base_url = self.base_url.strip().rstrip("/")
        if base_url == "https://service.cryptoracle.network":
            # Older environment examples omitted the API's /openapi prefix.
            base_url = _DEFAULT_BASE_URL
        try:
            parsed = urlsplit(base_url)
            valid_url = (
                parsed.scheme == "https"
                and bool(parsed.hostname)
                and not parsed.username
                and not parsed.password
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            valid_url = False
        if not valid_url:
            raise CryptoracleConfigurationError(
                "CRYPTORACLE_API_BASE_URL must be an HTTPS URL without "
                "credentials, query parameters or fragments"
            )
        object.__setattr__(self, "base_url", base_url)
        for attribute in ("api_key", "backup_api_key"):
            key = getattr(self, attribute).strip()
            if key.startswith("replace-with-"):
                key = ""
            if any(not " " <= character <= "~" for character in key):
                raise CryptoracleConfigurationError(
                    f"{attribute} must contain only printable ASCII characters"
                )
            object.__setattr__(self, attribute, key)
        if not self.api_keys:
            raise CryptoracleConfigurationError(
                "Set CRYPTORACLE_API_KEY or CRYPTORACLE_API_KEY_BACKUP"
            )

    @property
    def api_keys(self) -> tuple[str, ...]:
        """Usable, distinct keys in primary-first order."""
        return tuple(
            dict.fromkeys(key for key in (self.api_key, self.backup_api_key) if key)
        )

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "CryptoracleSettings":
        environment = os.environ if environment is None else environment
        return cls(
            base_url=environment.get("CRYPTORACLE_API_BASE_URL", _DEFAULT_BASE_URL),
            api_key=environment.get("CRYPTORACLE_API_KEY", ""),
            backup_api_key=environment.get("CRYPTORACLE_API_KEY_BACKUP", ""),
        )


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # The default urllib redirect handler can forward X-API-KEY to another host.
        return None


class CryptoracleClient:
    """POST JSON with a maximum of one request per distinct configured key.

    HTTP 401, 403, 429 and JSON business code 202 (invalid API key) trigger a
    backup attempt. Each new call starts with the primary key. This client does
    not load dotenv files. Other non-200 integer business codes raise API errors.
    """

    def __init__(self, settings: CryptoracleSettings, *, timeout: float = 15.0):
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise CryptoracleConfigurationError("timeout must be finite and positive")
        self.settings = settings
        self.timeout = timeout
        self._opener = build_opener(_NoRedirects())

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        timeout: float = 15.0,
    ) -> "CryptoracleClient":
        return cls(CryptoracleSettings.from_environment(environment), timeout=timeout)

    def post(self, endpoint: str, payload: Mapping[str, object]) -> object:
        """Query a provider-confirmed path, returning the decoded JSON response."""
        parsed = urlsplit(endpoint)
        if (
            not endpoint.startswith("/")
            or parsed.scheme
            or parsed.netloc
            or parsed.fragment
            or endpoint.startswith("//")
            or "\\" in endpoint
        ):
            raise CryptoracleConfigurationError(
                "endpoint must be a path beginning with / on the configured host"
            )
        url = self.settings.base_url + endpoint
        body = json.dumps(dict(payload), allow_nan=False).encode("utf-8")
        keys = self.settings.api_keys
        for index, key in enumerate(keys):
            request = Request(
                url,
                data=body,
                headers={"X-API-KEY": key, "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    http_status = response.code
                    raw = response.read()
            except HTTPError as error:
                status = error.code
                error.close()
                if status in {401, 403, 429} and index + 1 < len(keys):
                    continue
                raise CryptoracleAPIError(
                    f"Cryptoracle request failed (HTTP {status})", status_code=status
                ) from None
            except (URLError, OSError, HTTPException):
                raise CryptoracleAPIError(
                    "Cryptoracle request failed during transport"
                ) from None
            try:
                result = json.loads(raw)
            except (ValueError, UnicodeError):
                raise CryptoracleAPIError(
                    "Cryptoracle response is not valid JSON"
                ) from None
            code = result.get("code") if isinstance(result, dict) else None
            if isinstance(code, int) and not isinstance(code, bool) and code != 200:
                if code == 202 and index + 1 < len(keys):
                    continue
                raise CryptoracleAPIError(
                    f"Cryptoracle request failed (business code {code})",
                    status_code=http_status,
                    business_code=code,
                )
            return result
        raise AssertionError(
            "Cryptoracle settings must contain at least one usable key"
        )
