from datetime import date, timedelta

import pytest

from strategies.global_etf_rotation import DailyBar, GlobalETFConfig, rank_assets, run_monthly_rotation, select_assets


def _bars(values):
    start = date(2023, 1, 1)
    return [DailyBar((start + timedelta(days=i)).isoformat(), value, 1000) for i, value in enumerate(values)]


def test_rotation_rejects_empty_history():
    with pytest.raises(ValueError, match="must not be empty"):
        run_monthly_rotation({}, GlobalETFConfig())


def test_rank_and_select_are_deterministic_with_cash_defense():
    history = {"AAA": _bars([100 + i for i in range(320)]), "BBB": _bars([100] * 320)}
    ranked = rank_assets(history, "2023-10-01", lookbacks=(20,), volatility_window=10, mode="pure_momentum")
    targets = select_assets(ranked, top_k=1, max_weight=0.45, cash_weight=0.10)
    assert ranked[0].symbol == "AAA"
    assert targets == {"AAA": pytest.approx(0.45)}


def test_rotation_uses_prior_date_for_monthly_signal():
    history = {symbol: _bars([100 + i * (1 if symbol == "AAA" else 0) for i in range(320)]) for symbol in ("AAA", "BBB")}
    result = run_monthly_rotation(history, GlobalETFConfig(lookbacks=(20,), momentum_weights=(1.0,), volatility_window=10, top_k=1))
    assert result.rebalances
    assert all(item.as_of < item.date for item in result.rebalances)
