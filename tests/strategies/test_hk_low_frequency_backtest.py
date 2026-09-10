from datetime import date, timedelta

import pytest

from strategies.hk_low_frequency.backtest import (
    DailyBar,
    HKBacktestConfig,
    load_daily_csv,
    rank_symbols,
    run_monthly_backtest,
    select_targets,
)


def _bars(values: list[float]) -> list[DailyBar]:
    start = date(2023, 1, 1)
    return [DailyBar((start + timedelta(days=i)).isoformat(), value, 1_000) for i, value in enumerate(values)]


def test_load_daily_csv_parses_and_orders_rows(tmp_path):
    path = tmp_path / "700.csv"
    path.write_text("date,close,volume\n2023-01-02,11,100\n2023-01-01,10,90\n", encoding="utf-8")

    assert load_daily_csv(path) == [DailyBar("2023-01-01", 10.0, 90.0), DailyBar("2023-01-02", 11.0, 100.0)]


def test_load_daily_csv_rejects_missing_or_nonpositive_close(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("date,close,volume\n2023-01-01,,100\n", encoding="utf-8")

    with pytest.raises(ValueError, match="close"):
        load_daily_csv(path)


def test_backtest_rejects_empty_universe():
    with pytest.raises(ValueError, match="universe"):
        run_monthly_backtest({}, _bars([100.0] * 30), HKBacktestConfig())


def test_backtest_has_no_lookahead_and_produces_returns():
    history = {"AAA": _bars([100.0 + i for i in range(320)]), "BBB": _bars([100.0] * 320)}
    result = run_monthly_backtest(
        history,
        _bars([100.0] * 320),
        HKBacktestConfig(lookbacks=(20,), momentum_weights=(1.0,), volatility_window=10, top_k=1),
    )

    assert result.portfolio_returns
    assert len(result.portfolio_returns) == len(result.benchmark_returns)
    assert result.dates[0] > "2023-01-01"
    assert all(item.as_of < item.date for item in result.rebalances)
    assert all(item.turnover >= 0 for item in result.rebalances)


def test_ranking_and_target_weights_are_deterministic_and_capped():
    history = {"AAA": _bars([100.0 + i for i in range(320)]), "BBB": _bars([100.0] * 320)}
    ranked = rank_symbols(history, "2023-10-01", lookbacks=(20,), volatility_window=10, mode="pure_momentum")
    targets = select_targets(ranked, top_k=1, max_weight=0.12, cash_weight=0.02)

    assert [item.symbol for item in ranked] == ["AAA", "BBB"]
    assert sum(targets.values()) == pytest.approx(0.12)
    assert targets["AAA"] == pytest.approx(0.12)
