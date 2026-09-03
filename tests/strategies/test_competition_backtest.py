import pytest

from strategies.international_lite.backtest import BacktestConfig, run_backtest


def test_backtest_charges_turnover_and_reports_eligibility():
    result = run_backtest([0.02, -0.01, 0.01], [0.0, 1.0, 0.5], BacktestConfig(commission_bps=10, slippage_bps=5, holding_rate=1.0, average_turnover=1.5))
    assert result.net_returns[1] < -0.01
    assert result.metrics.cumulative_return < 0.02
    assert result.eligible is True


def test_backtest_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        run_backtest([], [], BacktestConfig())
    with pytest.raises(ValueError):
        run_backtest([0.1], [0.0], BacktestConfig(commission_bps=-1))
