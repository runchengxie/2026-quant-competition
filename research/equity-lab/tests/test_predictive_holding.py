from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from equity_lab.portfolio.rank_buffer import choose
from equity_lab.portfolio.cash_rebalance import rebalance
from equity_lab.predictive.holding_data import prepare_holding, holding_folds
from equity_lab.predictive.holding_account import replay_holdings


def test_buffer_retains_previous_names_at_boundary_but_not_past_it():
    scores = {"A": 3, "B": 2, "C": 1, "D": 0}
    assert choose(scores, ["C", "D"], top_n=2, buffer=1) == ["A", "C"]
    assert choose(scores, ["C", "D"], top_n=2, buffer=0) == ["A", "B"]
    with pytest.raises(ValueError, match="CONSTANT_SCORES"):
        choose({"A": 0, "B": 0}, [], top_n=2)


def test_cash_funding_rebalance_and_unchanged_positions():
    first = rebalance(1.0, {}, {"A": 100.0}, {"A": 1.0}, 40)
    assert first["cash"] == pytest.approx(0, abs=1e-12)
    assert first["quantities"]["A"] == pytest.approx(1 / 1.004 / 100)
    assert first["cost"] == pytest.approx(0.004 / 1.004)
    unchanged = rebalance(
        first["cash"], first["quantities"], {"A": 110.0}, {"A": 1.0}, 40
    )
    assert unchanged["cost"] == 0
    assert unchanged["quantities"] == first["quantities"]
    final = rebalance(unchanged["cash"], unchanged["quantities"], {"A": 110.0}, {}, 40)
    assert final["cash"] == pytest.approx(1.1 * (1 - 0.004) / (1 + 0.004))
    assert not final["quantities"]


def raw_fixture(count=230, candidates=55):
    days = pd.date_range("2025-01-01", periods=count, freq="B")
    schedule = pd.DataFrame(
        {
            "open": days.tz_localize("UTC") + pd.Timedelta(hours=14),
            "close": days.tz_localize("UTC") + pd.Timedelta(hours=21),
        },
        index=days,
    )
    rows = []
    for i, day in enumerate(days):
        for j in range(candidates):
            opening = 100 + j + i * 0.02
            closing = opening * (1 + 0.01 * np.sin(i * 0.31 + j * 0.47))
            rows.append(
                dict(
                    TradeDate=day,
                    ResearchKey=f"unresolved:S{j:03}",
                    Ticker=f"S{j:03}",
                    open_price=opening,
                    close_price=closing,
                    high_price=max(opening, closing) * 1.001,
                    low_price=min(opening, closing) * 0.999,
                    dollar_volume=20_000_000 + j * 1000,
                    median_spread=0.0001,
                    valid_quote_minutes=400,
                    active_trade_minutes=400,
                )
            )
    return pd.DataFrame(rows), schedule


def test_multiday_labels_use_exact_calendar_and_missing_intermediate_session():
    raw, schedule = raw_fixture(35, 2)
    frame = prepare_holding(raw, schedule, 5)
    first = frame[
        (frame.candidate_id == "unresolved:S000") & (frame.date == "2025-01-01")
    ].iloc[0]
    end = raw[(raw.Ticker == "S000") & (raw.TradeDate == schedule.index[5])].iloc[0]
    start = raw[(raw.Ticker == "S000") & (raw.TradeDate == schedule.index[1])].iloc[0]
    assert first.target == pytest.approx(end.close_price / start.open_price - 1)
    assert first.label_end == schedule.iloc[5]["close"]
    raw = raw[~((raw.Ticker == "S000") & (raw.TradeDate == schedule.index[3]))]
    missing = prepare_holding(raw, schedule, 5)
    assert pd.isna(missing[missing.candidate_id == "unresolved:S000"].iloc[0].target)


def test_common_folds_reserve_max_label_horizon_and_enforce_training_floor():
    days = [(date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(230)]
    folds = holding_folds(days)
    assert list(map(len, folds)) == [40, 40]
    assert folds[0][0] == days[-101]
    assert folds[-1][-1] == days[-22]
    with pytest.raises(ValueError):
        holding_folds(days[:220])


def test_known_action_boundary_is_quarantined_without_adjusting_prices():
    raw, schedule = raw_fixture(35, 2)
    raw["KnownActionBoundary"] = (raw.Ticker == "S000") & (
        raw.TradeDate == schedule.index[3]
    )
    frame = prepare_holding(raw, schedule, 5)
    assert pd.isna(frame[frame.candidate_id == "unresolved:S000"].iloc[0].target)
    assert frame.iloc[0].open_price == raw.iloc[0].open_price
    observations, calendar, dates, plans = simple_account_inputs()
    observations[(calendar[2], "A")]["action_boundary"] = True
    blocked = replay_holdings(
        observations, calendar, dates, plans, horizon=2, fee_bps=0, delay=0
    )
    assert blocked["reason"] == "KNOWN_ACTION_BOUNDARY"
    assert blocked["metrics"] is None


def simple_account_inputs():
    calendar = [(date(2026, 1, 1) + timedelta(days=i)).isoformat() for i in range(7)]
    observations = {
        (day, "A"): {"open": 100 + i * 10, "close": 110 + i * 10, "valid": True}
        for i, day in enumerate(calendar)
    }
    plans = [
        {"date": calendar[0], "selected": ["A"], "reason": None},
        {"date": calendar[2], "selected": ["A"], "reason": None},
    ]
    return observations, calendar, calendar[:4], plans


def test_holdings_drift_terminal_fees_and_common_delay_grid():
    observations, calendar, dates, plans = simple_account_inputs()
    original = replay_holdings(
        observations, calendar, dates, plans, horizon=2, fee_bps=40, delay=0
    )
    delayed = replay_holdings(
        observations, calendar, dates, plans, horizon=2, fee_bps=40, delay=1
    )
    assert original["status"] == delayed["status"] == "completed"
    assert original["requested_dates"] == delayed["requested_dates"] == 5
    assert original["metrics"]["net_return"] == pytest.approx(
        150 / 110 * (1 - 0.004) / (1 + 0.004) - 1
    )
    assert delayed["metrics"]["net_return"] == pytest.approx(
        160 / 120 * (1 - 0.004) / (1 + 0.004) - 1
    )
    assert original["periods"][2]["trade_cost"] == 0
    assert delayed["periods"][0]["equity"] == 1
    assert not original["periods"][-1]["quantities"]
    assert sum(
        row["price_pnl"] - row["cost"] for row in original["periods"]
    ) == pytest.approx(original["metrics"]["net_return"])


def test_selected_missing_price_blocks_without_dropping_or_stitching():
    observations, calendar, dates, plans = simple_account_inputs()
    del observations[(calendar[2], "A")]
    result = replay_holdings(
        observations, calendar, dates, plans, horizon=2, fee_bps=0, delay=0
    )
    assert result["status"] == "blocked"
    assert result["metrics"] is None
    assert result["reason"] == "MISSING_HELD_OR_SELECTED_PRICE"
    assert result["valid_dates"] == 1
    plans[0]["reason"] = "CONSTANT_SCORES"
    assert (
        replay_holdings(
            observations, calendar, dates, plans, horizon=2, fee_bps=0, delay=0
        )["reason"]
        == "CONSTANT_SCORES"
    )


def test_full_synthetic_holding_workflow_has_fixed_fits_and_complete_grid(tmp_path):
    pytest.importorskip("sklearn")
    from equity_lab.predictive.holding import run_holding

    raw, schedule = raw_fixture()
    report = run_holding(raw, schedule, tmp_path / "run")
    assert 48 <= report["fit_attempts"] <= 56
    assert len(report["accounts"]) == 168
    assert {r["horizon"] for r in report["accounts"]} == {5, 20}
    assert (tmp_path / "run/observations.csv").is_file()
    assert (tmp_path / "run/decisions.csv").is_file()
    assert (tmp_path / "run/calendar.csv").is_file()
    assert 24 <= (tmp_path / "run/attempts-5.jsonl").read_text().count("\n") <= 28
    assert all(
        r["training_latest_label_end"] < r["decision_at"]
        and r["inner_latest_label_end"] < r["inner_decision_at"]
        for r in report["models"]
    )


def test_installed_synthetic_delivery_input_needs_no_external_prices():
    from equity_lab.predictive.holding_demo import synthetic_input

    raw, schedule = synthetic_input()
    assert len(schedule) == 230
    assert raw.ResearchKey.nunique() == 55
    assert raw.ResearchKey.str.startswith("SYNTHETIC").all()
