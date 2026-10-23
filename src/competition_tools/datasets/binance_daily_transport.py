"""Credential-free public archive reads in a killable deadline-bound process."""

import subprocess
import sys
import urllib.error
import urllib.request

from .binance_daily import PRODUCTS, daily_archive_url


def validate_url(url: str) -> None:
    # Match a constructed URL exactly; reject credentials, redirects and queries.
    stem = url.removesuffix(".CHECKSUM")
    name = stem.rsplit("/", 1)[-1]
    for product in PRODUCTS:
        prefix = product + "-1d-"
        if name.startswith(prefix) and name.endswith(".zip"):
            if stem == daily_archive_url(product, name[len(prefix) : -4]):
                return
    raise ValueError("UNAPPROVED_DAILY_URL")


def run_worker(
    command: list[str], *, timeout: float, max_bytes: int
) -> tuple[int, bytes]:
    if timeout <= 0 or max_bytes <= 0:
        raise ValueError("INVALID_DAILY_TRANSPORT_BUDGET")
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.communicate()
        raise TimeoutError("DAILY_TRANSPORT_DEADLINE") from exc
    if process.returncode or len(output) < 4 or len(output) > max_bytes + 4:
        raise ValueError("UNKNOWN_DAILY_TRANSFER_SPEND")
    return int.from_bytes(output[:4], "big"), output[4:]


class DailyTransport:
    def fetch(self, url: str, *, max_bytes: int, timeout: float) -> tuple[int, bytes]:
        validate_url(url)
        return run_worker(
            [sys.executable, "-m", __name__, url, str(max_bytes), str(timeout)],
            timeout=timeout,
            max_bytes=max_bytes,
        )


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main() -> None:
    url, limit, timeout = sys.argv[1:]
    validate_url(url)
    opener = urllib.request.build_opener(NoRedirect())
    try:
        response = opener.open(
            urllib.request.Request(
                url, headers={"User-Agent": "competition-daily-extension/1"}
            ),
            timeout=float(timeout),
        )
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        body = response.read(int(limit) + 1)
        status = response.status
    if len(body) > int(limit):
        raise ValueError("DAILY_RESPONSE_TOO_LARGE")
    sys.stdout.buffer.write(int(status).to_bytes(4, "big") + body)


if __name__ == "__main__":
    main()
