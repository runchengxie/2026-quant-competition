"""Account-guarded read-only SDK lifetime, with redacted failures."""

import logging
import math
import re
from pathlib import Path

from .gateway import load_paper_endpoint


class PaperReadError(ValueError):
    """Stable diagnostic code; never attach SDK or account details."""


class PaperReadSession:
    def __init__(
        self, connection_file: Path, *, timeout: float = 8, client_factory=None
    ):
        self.connection_file = connection_file
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (float, int))
            or not math.isfinite(timeout)
            or not 0 < timeout <= 30
        ):
            raise PaperReadError("INVALID_READ_TIMEOUT")
        self.timeout = timeout
        self.client_factory = client_factory
        self.client = None
        self.account_check = {"status": "not_checked", "count": None}
        self.logger = logging.getLogger("ib_insync")
        self.previous_level = None

    def __enter__(self):
        if self.previous_level is not None:
            raise PaperReadError("SESSION_ALREADY_ACTIVE")
        try:
            endpoint = load_paper_endpoint(self.connection_file)
        except ValueError:
            raise PaperReadError("INVALID_PAPER_CONNECTION") from None
        factory = self.client_factory
        if factory is None:
            try:
                from ib_insync import IB
            except ImportError:
                raise PaperReadError("BROKER_DATA_PROFILE_REQUIRED") from None
            factory = IB
        self.previous_level = self.logger.level
        self.logger.setLevel(logging.CRITICAL)
        try:
            self.client = factory()
            self.client.connect(
                endpoint["host"],
                endpoint["port"],
                clientId=endpoint["client_id"],
                timeout=self.timeout,
                readonly=True,
            )
            if not self.client.isConnected():
                raise PaperReadError("GATEWAY_API_NOT_READY")
            accounts = self.client.managedAccounts()
            if (
                not isinstance(accounts, (list, tuple))
                or len(accounts) != 1
                or not isinstance(accounts[0], str)
                or not re.fullmatch(r"DU[A-Za-z0-9_]+", accounts[0])
            ):
                self.account_check = {"status": "blocked", "count": None}
                raise PaperReadError("PAPER_ACCOUNT_REQUIRED")
            self.account_check = {"status": "paper_single", "count": 1}
            return self.client
        except Exception as error:
            code = (
                str(error) if isinstance(error, PaperReadError) else "API_READ_FAILED"
            )
            self._close()
            raise PaperReadError(code) from None
        except BaseException:
            self._close()
            raise

    def _close(self):
        try:
            if self.client is not None:
                self.client.disconnect()
        except Exception:
            raise PaperReadError("API_DISCONNECT_FAILED") from None
        finally:
            self.client = None
            if self.previous_level is not None:
                self.logger.setLevel(self.previous_level)
                self.previous_level = None

    def __exit__(self, exc_type, exc_value, traceback):
        self._close()
        return False
