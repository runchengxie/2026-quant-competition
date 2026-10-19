from datetime import datetime
import math
import os
import subprocess
import sys

import polars as pl
import pytest

from crypto_mm.audit import audit_fundings, audit_orderbook, audit_trades
from crypto_mm.backtest import build_backtest_engine
from crypto_mm.config import BacktestConfig, SimulationConfig, StrategyConfig
from crypto_mm.events import MarketEventBatch, OrderBookEvent, TradeEvent
from crypto_mm.features import FeatureEngineConfig
from crypto_mm.order_manager import OrderManager, OrderManagerConfig
from crypto_mm.market_data import iter_trade_events
from crypto_mm.research.analyze_signals import build_signal_samples
from crypto_mm.strategy import DesiredQuote


@pytest.mark.parametrize(
    "factory,field",
    [
        (StrategyConfig, "volatility_sample_interval_ns"),
        (StrategyConfig, "volatility_window"),
        (FeatureEngineConfig, "volatility_sample_interval_ns"),
        (FeatureEngineConfig, "volatility_window"),
        (SimulationConfig, "placement_latency_ns"),
        (SimulationConfig, "cancellation_latency_ns"),
        (SimulationConfig, "sample_interval_ns"),
    ],
)
@pytest.mark.parametrize("value", [math.nan, math.inf, 1.5, True])
def test_timing_and_window_settings_reject_nonintegers(factory, field, value):
    with pytest.raises(ValueError, match="integer"):
        factory(**{field: value})


@pytest.mark.parametrize(
    "audit,column,values",
    [
        (audit_trades, "price", [math.nan]),
        (audit_trades, "size", [math.inf]),
        (audit_fundings, "funding_rate", [-math.inf]),
    ],
)
def test_audit_flags_nonfinite_values(tmp_path, audit, column, values):
    data = {
        "datetime": pl.Series([datetime(2026, 3, 19)], dtype=pl.Datetime("ns")),
        "price": [100.0],
        "size": [1.0],
        "is_maker_ask": [False],
        "funding_rate": [0.0],
    }
    data[column] = values
    path = tmp_path / "2026-03-19.parquet"
    pl.DataFrame(data).write_parquet(path)
    assert audit(path)["quality"]["nonfinite_values"] == 1


def test_audit_rejects_negative_but_ordered_book_prices(tmp_path):
    data = {"datetime": pl.Series([datetime(2026, 3, 19)], dtype=pl.Datetime("ns"))}
    for level in range(1, 21):
        data[f"bid_price_{level}"] = [-100.0 - level]
        data[f"ask_price_{level}"] = [-100.0 + level]
        data[f"bid_qty_{level}"] = [1.0]
        data[f"ask_qty_{level}"] = [1.0]
    path = tmp_path / "2026-03-19.parquet"
    pl.DataFrame(data).write_parquet(path)
    assert audit_orderbook(path)["quality"]["nonpositive_price_rows"] == 1


def test_subsecond_sampling_labels_use_elapsed_seconds(tmp_path):
    path = tmp_path / "orderbook/2026-03-19.parquet"
    path.parent.mkdir()
    pl.DataFrame(
        {
            "datetime": [0, 500_000_000, 1_000_000_000],
            "bid_price_1": [99.0, 109.0, 119.0],
            "ask_price_1": [101.0, 111.0, 121.0],
            "bid_qty_1": [1.0] * 3,
            "ask_qty_1": [1.0] * 3,
        }
    ).write_parquet(path)
    result = build_signal_samples(
        ("2026-03-19",),
        data_root=tmp_path,
        feature_config=FeatureEngineConfig(
            volatility_sample_interval_ns=500_000_000, volatility_window=1
        ),
    )
    assert result["future_return_1s_bps"][0] == pytest.approx(10_000 * math.log(1.2))


def test_intrabatch_inventory_peak_is_not_lost_after_offsetting_fills():
    engine, tracker = build_backtest_engine(
        "B0",
        BacktestConfig(
            simulation=SimulationConfig(
                placement_latency_ns=0, cancellation_latency_ns=0
            )
        ),
    )
    engine.run(
        [
            MarketEventBatch(
                0, (), (OrderBookEvent(0, (99.9,), (100.1,), (0.0,), (0.0,)),), ()
            ),
            MarketEventBatch(
                1,
                (TradeEvent(1, 99.9, 0.1, False), TradeEvent(1, 100.1, 0.1, True)),
                (),
                (),
            ),
        ]
    )
    assert len(engine.fills) == 2
    assert engine.account.inventory == 0
    assert tracker.metrics(engine.account).max_absolute_inventory == pytest.approx(0.1)


def test_distinct_high_price_ticks_require_replacement():
    manager = OrderManager(OrderManagerConfig(0, 0, 1.0))
    manager.reconcile(DesiredQuote(1e9, 0.1, None, 0), 0)
    assert manager.reconcile(DesiredQuote(1e9 + 0.1, 0.1, None, 0), 1)


def test_plot_help_does_not_try_to_read_market_data(tmp_path):
    env = {**os.environ, "DATA_ROOT": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "-m", "crypto_mm.commands.plot_results", "--help"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert not list(tmp_path.rglob("*.png"))


def test_datetime_storage_unit_is_normalized_to_nanosecond_events(tmp_path):
    path = tmp_path / "2026-03-19.parquet"
    timestamp = datetime(2026, 3, 19)
    pl.DataFrame(
        {
            "datetime": pl.Series([timestamp], dtype=pl.Datetime("us")),
            "price": [100.0],
            "size": [1.0],
            "is_maker_ask": [False],
        }
    ).write_parquet(path)
    expected = pl.Series([timestamp], dtype=pl.Datetime("ns")).cast(pl.Int64)[0]
    assert next(iter_trade_events(path)).timestamp_ns == expected


def test_signal_horizons_reject_an_unrepresentable_grid(tmp_path):
    with pytest.raises(ValueError, match="divide"):
        build_signal_samples(
            ("2026-03-19",),
            data_root=tmp_path,
            feature_config=FeatureEngineConfig(
                volatility_sample_interval_ns=2_000_000_000
            ),
        )
