"""Optional study signals are lagged and the CLI needs no private config."""

import os
import subprocess
import sys
from datetime import date, timedelta

import pytest
from equity_lab.study.run import evaluate_study


def bars(days=315):
    return {
        "dates": [
            (date(2023, 1, 1) + timedelta(days=i)).isoformat() for i in range(days)
        ],
        "close": {"A": [100.0] * days, "B": [100.0] * days},
    }


def test_constant_prices_charge_scored_entry_without_warmup_trades():
    result = evaluate_study(bars(), "equal_weight", fee_bps=20, quote_currency="USD")
    assert len(result["net"]["periods"]) == 63
    assert result["net"]["periods"][0]["date"] == "2023-09-10"
    assert result["metrics"]["gross_return"] == 0
    assert result["metrics"]["net_return"] == pytest.approx(1 / 1.002 - 1)
    assert result["metrics"]["max_drawdown"] == pytest.approx(1 - 1 / 1.002)
    assert result["metrics"]["turnover"] == pytest.approx(1 / 1.002)


@pytest.mark.parametrize(
    "strategy", ["equal_weight", "buy_hold", "momentum_20d", "sma_cross"]
)
def test_future_prices_cannot_change_earlier_periods(strategy):
    original = bars()
    changed = bars()
    for i in range(270, 315):
        changed["close"]["A"][i] = 200.0
    before = evaluate_study(original, strategy, fee_bps=20, quote_currency="USD")
    after = evaluate_study(changed, strategy, fee_bps=20, quote_currency="USD")
    assert before["net"]["periods"][:18] == after["net"]["periods"][:18]


def test_positive_momentum_uses_previous_close():
    data = bars()
    for i in range(252, 315):
        data["close"]["A"][i] = 200.0
    result = evaluate_study(data, "momentum_20d", fee_bps=0, quote_currency="USD")
    assert result["net"]["periods"][0]["exposure"] == 0
    assert result["net"]["periods"][1]["exposure"] == 1
    assert result["metrics"]["net_return"] == 0


def test_module_help_needs_no_data_configuration():
    env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in {
            "DATA_ROOT",
            "WORKSPACE_CONFIG",
            "CONFIG_ROOT",
            "PYTHONPATH",
            "PYTHONHOME",
        }
    }
    child = subprocess.run(
        [sys.executable, "-m", "equity_lab.study", "--help"],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert child.returncode == 0
    assert "--job" in child.stdout


@pytest.mark.parametrize("price", [0, float("nan"), float("inf")])
def test_invalid_warmup_price_is_rejected_before_target_allocation(price):
    data = bars()
    data["close"]["A"][251] = price
    with pytest.raises(ValueError):
        evaluate_study(data, "buy_hold", fee_bps=20, quote_currency="USD")
