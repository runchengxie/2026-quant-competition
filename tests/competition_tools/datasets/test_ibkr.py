"""Broker acquisition can request history, but has no order interface."""

from types import SimpleNamespace

from competition_tools.datasets.ibkr import collect_pilot


class HistoricalOnly:
    def __init__(self, nonempty=True):
        self.calls = []
        self.disconnected = False
        self.nonempty = nonempty
        self.connected = False

    def connect(self, host, port, **kwargs):
        self.connected = True
        assert host == "127.0.0.1" and port == 4002
        assert kwargs["readonly"] is True

    def reqHistoricalData(self, contract, **kwargs):
        assert kwargs["durationStr"] == "1 M" and kwargs["barSizeSetting"] == "1 day"
        assert kwargs["whatToShow"] == "TRADES" and kwargs["useRTH"] is True
        self.calls.append(contract)
        return (
            [
                SimpleNamespace(
                    date="2024-01-02", open=1, high=2, low=0.5, close=1.5, volume=10
                )
            ]
            if self.nonempty
            else []
        )

    def disconnect(self):
        self.disconnected = True


def test_readonly_pilot_disconnects_and_records_unknown_availability(tmp_path):
    client = HistoricalOnly()
    value = collect_pilot(
        {
            "market": "US",
            "quote_currency": "USD",
            "products": ["SPY"],
            "contracts": [
                {
                    "product": "SPY",
                    "con_id": 123,
                    "exchange": "SMART",
                    "currency": "USD",
                }
            ],
            "start": "2024-01-01",
            "end": "2024-01-31",
            "budget": {"requests": 100, "bytes": 100000, "seconds": 1800},
        },
        {"host": "127.0.0.1", "port": 4002, "client_id": 999},
        tmp_path,
        client=client,
        contract_factory=lambda **kwargs: kwargs,
        sleep=lambda seconds: None,
    )
    assert (
        value["status"] == "partial"
    )  # One-month pilot is not requested multi-year coverage.
    assert value["available_at"] is None
    assert value["coverage"]["SPY"]["rows"] == 1
    assert client.disconnected
    assert len(client.calls) == 1


def test_contract_market_mismatch_rejected_before_connection(tmp_path):
    import pytest

    client = HistoricalOnly()
    spec = {
        "market": "US",
        "quote_currency": "USD",
        "products": ["SPY"],
        "contracts": [
            {"product": "SPY", "con_id": 123, "exchange": "SEHK", "currency": "HKD"}
        ],
        "start": "2024-01-01",
        "end": "2024-01-31",
        "budget": {"requests": 100, "bytes": 100000, "seconds": 1800},
    }
    with pytest.raises(ValueError, match="CONTRACT_MARKET"):
        collect_pilot(
            spec,
            {"host": "127.0.0.1", "port": 4002, "client_id": 999},
            tmp_path,
            client=client,
            contract_factory=lambda **kwargs: kwargs,
            sleep=lambda seconds: None,
        )
    assert not client.connected
    assert not client.calls


def test_empty_pilot_stops_before_expanding(tmp_path):
    client = HistoricalOnly(False)
    value = collect_pilot(
        {
            "market": "US",
            "quote_currency": "USD",
            "products": ["SPY", "AAPL"],
            "contracts": [
                {
                    "product": "SPY",
                    "con_id": 123,
                    "exchange": "SMART",
                    "currency": "USD",
                }
            ],
            "start": "2024-01-01",
            "end": "2024-01-31",
            "budget": {"requests": 100, "bytes": 100000, "seconds": 1800},
        },
        {"host": "127.0.0.1", "port": 4002, "client_id": 999},
        tmp_path,
        client=client,
        contract_factory=lambda **kwargs: kwargs,
        sleep=lambda seconds: None,
    )
    assert value["gaps"][0]["reason"] == "EMPTY_HISTORICAL_RESPONSE"
    assert len(client.calls) == 1
    assert client.disconnected
