from decimal import Decimal

import pytest

from strategies.international_lite import (
    DailyBar,
    build_target_set,
    check_daily_continuity,
    compute_features,
    rank_symbols,
)


def bars(closes, start="2026-01-01"):
    return tuple(DailyBar(f"2026-01-{i:02d}", close, 1000 + i) for i, close in enumerate(closes, 1))


def test_features_use_only_daily_ohlcv_history():
    result = compute_features(bars([100, 101, 102, 104, 105]), lookback=3)
    assert result.momentum > 0
    assert result.volatility >= 0
    assert result.average_volume > 0


def test_rank_and_target_generation_are_deterministic():
    history = {
        "1321.T": bars([100, 100, 101, 104, 105]),
        "1306.T": bars([100, 101, 100, 100, 100]),
    }
    ranked = rank_symbols(history, lookback=3)
    assert ranked[0][0] == "1321.T"
    targets = build_target_set("japan-lite", "JP", history, top_k=1, lookback=3, as_of="2026-09-03T00:00:00Z")
    assert targets.targets[0].symbol == "1321.T"
    assert targets.targets[0].weight == Decimal("1")


def test_continuity_flags_duplicates_and_large_gaps():
    report = check_daily_continuity(["2026-01-01", "2026-01-02", "2026-01-10"], max_gap_days=5)
    assert not report.passed
    assert report.max_gap_days == 8
    with pytest.raises(ValueError):
        check_daily_continuity(["2026-01-01", "2026-01-01"])
