"""Daily bulk identity does not change the v1 pilot contract."""

import copy
import json
import tempfile
from pathlib import Path
import pytest

from competition_tools.datasets.spec import load_spec
from competition_tools.datasets.daily_spec import validate_daily_spec


def daily_spec():
    return {
        "schema": "competition.dataset_spec.v2",
        "dataset_id": "us-fixed",
        "version": "v1",
        "source": "ibkr_daily",
        "market": "US",
        "products": ["AAPL"],
        "benchmark": "SPY",
        "quote_currency": "USD",
        "start": "2024-07-01",
        "end": "2024-07-05",
        "timezone": "America/New_York",
        "calendar": "XNYS",
        "price_basis": "split_adjusted",
        "universe_status": "fixed_current",
        "budget": {"requests": 120, "bytes": 33554432, "seconds": 2400},
        "connection_file": str(Path(tempfile.gettempdir()) / "paper.json"),
        "contracts": [
            {
                "product": p,
                "symbol": p,
                "exchange": "SMART",
                "currency": "USD",
                "role": role,
            }
            for p, role in [("AAPL", "stock"), ("SPY", "benchmark")]
        ],
    }


def test_load_v2_dispatch(tmp_path):
    spec = daily_spec()
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    assert load_spec(path) == spec


@pytest.mark.parametrize(
    "change",
    [
        {"calendar": "XHKG"},
        {"quote_currency": "HKD"},
        {"price_basis": "raw"},
        {"source": "ibkr"},
        {"universe_status": "point_in_time"},
        {"unknown": "secret"},
        {"end": "2023-01-01"},
        {"products": ["SPY"]},
        {"products": ["AAPL", "AAPL"]},
        {"budget": {"requests": True, "bytes": 1000, "seconds": 60}},
        {"budget": {"requests": 121, "bytes": 1000, "seconds": 60}},
    ],
)
def test_invalid_daily_identity_rejected(change):
    with pytest.raises(ValueError):
        validate_daily_spec(daily_spec() | change)


def test_contract_roles_and_aliases_are_unique():
    for key, value in [("role", "benchmark"), ("symbol", "SPY"), ("currency", "HKD")]:
        spec = copy.deepcopy(daily_spec())
        spec["contracts"][0][key] = value
        with pytest.raises(ValueError):
            validate_daily_spec(spec)
