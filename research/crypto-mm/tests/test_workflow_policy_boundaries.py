"""Daily policies remain separate from replay, maker state and configuration."""

import math
import os
import subprocess
import sys
from datetime import date, timedelta

import pytest

from crypto_mm.data.daily_prices import validate_prices
from crypto_mm.portfolio.daily import (
    build_ablation_targets,
    build_control_targets,
    build_study_targets,
)
from crypto_mm.portfolio.rebalance import weekly_flags
from crypto_mm.signals.daily_trend import hysteresis_states, select_trend_products


def bars(constant=False):
    return {
        "dates": [
            (date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(270)
        ],
        "close": {
            "A": [
                100.0 if constant else 100 + i / 10 + math.sin(i / 5)
                for i in range(270)
            ]
        },
    }


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), -1.0])
def test_price_contract_rejects_nonfinite_nonpositive_and_boolean(bad):
    value = bars()
    value["close"]["A"][10] = bad
    with pytest.raises(ValueError, match="INVALID_ACCOUNTING_PRICES"):
        validate_prices(value)


def test_hysteresis_retains_state_between_thresholds():
    assert hysteresis_states([100.0] * 200 + [105.0, 100.0, 95.0])[-3:] == [
        True,
        True,
        False,
    ]


def test_trend_selection_does_not_read_future_prices():
    value = bars()
    before = select_trend_products(value["close"], ["A"], 251)
    value["close"]["A"][252:] = [1.0] * 18
    assert select_trend_products(value["close"], ["A"], 251) == before == ["A"]


def test_strict_zero_volatility_remains_cash_and_fixed_exposure_stays_explicit():
    result = build_control_targets(bars(constant=True), "ew_vol40_strict")
    assert result["targets"] == [{}] * 18
    assert result["diagnostics"]["zero_volatility_decisions"] == 18
    assert all(
        sum(t.values()) == pytest.approx(0.6)
        for t in build_control_targets(bars(), "ew_fixed60")["targets"]
    )


def test_public_policy_helpers_remain_the_same_function_objects():
    from crypto_mm.daily.ablation import build_targets, hysteresis_states as old_states
    from crypto_mm.daily.controls import build_control_targets as old_controls
    from crypto_mm.daily.study_accounting import validate_prices as old_prices
    from crypto_mm.daily.weekly import weekly_flags as old_flags

    assert build_targets is build_ablation_targets
    assert old_controls is build_control_targets
    assert old_states is hysteresis_states
    assert old_prices is validate_prices
    assert old_flags is weekly_flags


def test_legacy_equal_weight_study_keeps_buy_and_hold_weight_drift():
    value = bars()
    value["close"]["B"] = [100.0] * 270
    targets = build_study_targets(value, "equal_weight")
    assert targets[0] == pytest.approx({"A": 0.5, "B": 0.5})
    assert targets[1]["A"] > 0.5
    assert targets[1]["B"] < 0.5
    with pytest.raises(ValueError, match="INVALID_CRYPTO_STUDY"):
        build_study_targets(value, "unknown")


def test_weekly_calendar_always_allocates_initially_then_on_monday():
    assert weekly_flags(["2024-01-03", "2024-01-04", "2024-01-08"]) == [
        True,
        False,
        True,
    ]


def test_pure_policy_imports_do_not_load_evaluators_or_maker(tmp_path):
    code = """
import sys
from crypto_mm.data.daily_prices import validate_prices
from crypto_mm.signals.daily_trend import hysteresis_states
from crypto_mm.portfolio.daily import build_control_targets
from crypto_mm.portfolio.rebalance import weekly_flags
for prefix in ('crypto_mm.daily', 'crypto_mm.engine', 'crypto_mm.strategy', 'crypto_mm.paths', 'matplotlib', 'polars'):
    assert not any(n == prefix or n.startswith(prefix + '.') for n in sys.modules), prefix
"""
    environment = {
        k: v
        for k, v in os.environ.items()
        if k.upper()
        not in {"DATA_ROOT", "CONFIG_ROOT", "WORKSPACE_CONFIG", "XDG_CONFIG_HOME"}
    }
    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
