"""Network workers have an absolute deadline rather than only read inactivity."""

import sys
import time

import pytest


def test_absolute_worker_timeout():
    from competition_tools.datasets.binance_daily_transport import run_worker

    started = time.monotonic()
    with pytest.raises(TimeoutError):
        run_worker([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1, max_bytes=10)
    assert time.monotonic() - started < 10


@pytest.mark.parametrize("url", ["http://data.binance.vision/x", "https://evil.test/x", "https://user:secret@data.binance.vision/x", "https://data.binance.vision/../private"])
def test_transport_rejects_non_allowlisted_urls_without_starting_worker(url):
    from competition_tools.datasets.binance_daily_transport import DailyTransport

    with pytest.raises(ValueError):
        DailyTransport().fetch(url, max_bytes=100, timeout=1)
