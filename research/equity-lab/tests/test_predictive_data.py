import pandas as pd
import pytest

from equity_lab.predictive.data import freeze_inputs, monthly_membership, prepare_daily


def schedule():
    dates = pd.bdate_range("2026-01-01", periods=65)
    return pd.DataFrame(
        {
            "open": pd.to_datetime([f"{d.date()}T14:30:00Z" for d in dates]),
            "close": pd.to_datetime([f"{d.date()}T21:00:00Z" for d in dates]),
        },
        index=dates,
    )


def daily():
    return pd.DataFrame(
        [
            {
                "TradeDate": str(d.date()),
                "Ticker": ticker,
                "ResearchKey": "unresolved:" + ticker,
                "open_price": 10.0,
                "close_price": 11.0,
                "high_price": 12.0,
                "low_price": 9.0,
                "dollar_volume": 20_000_000.0,
                "median_spread": 0.01,
                "valid_quote_minutes": 390,
                "active_trade_minutes": 195,
            }
            for d in schedule().index
            for ticker in ["BRK.B", "A"]
        ]
    )


def test_labels_use_exact_next_session_and_preserve_dotted_candidates():
    raw = daily()
    raw = raw[~((raw.Ticker == "A") & (raw.TradeDate == "2026-01-02"))]
    result = prepare_daily(raw, schedule())
    a = result[(result.ticker == "A") & (result.date == "2026-01-01")].iloc[0]
    assert pd.isna(a.target)
    assert a.label_reason == "missing_next_session"
    assert "BRK.B" in set(result.ticker)
    b = result[(result.ticker == "BRK.B") & (result.date == "2026-01-01")].iloc[0]
    assert b.target == pytest.approx(0.1)
    assert b.range_fraction == pytest.approx(0.3)
    assert b.active_fraction == 0.5


def test_membership_uses_complete_prior_sessions_and_lagged_price():
    raw = daily()
    raw.loc[raw.TradeDate == "2026-02-02", "dollar_volume"] = 1
    frame = prepare_daily(raw, schedule())
    members = monthly_membership(frame, cap=1)
    feb = members[members.month == "2026-02"]
    assert feb.candidate_id.tolist() == ["unresolved:A"]
    assert feb.iloc[0].mean_dollar_volume == 20_000_000
    missing = raw[~((raw.Ticker == "A") & (raw.TradeDate == "2026-01-15"))]
    members = monthly_membership(prepare_daily(missing, schedule()), cap=500)
    assert members[members.month == "2026-02"].ticker.tolist() == ["BRK.B"]


def test_duplicate_identity_session_and_invalid_ohlc_fail_closed():
    raw = daily()
    with pytest.raises(ValueError, match="Duplicate"):
        prepare_daily(pd.concat([raw, raw.iloc[:1]]), schedule())
    raw.loc[0, "high_price"] = float("inf")
    result = prepare_daily(raw, schedule())
    invalid = result[(result.ticker == "BRK.B") & (result.date == "2026-01-01")].iloc[0]
    assert pd.isna(invalid.session_return)
    assert not invalid.price_valid


def test_short_session_denominator_and_identity_break():
    cal = schedule()
    cal.loc[cal.index[0], "close"] = pd.Timestamp("2026-01-01T18:00:00Z")
    raw = daily()
    raw.loc[0, ["valid_quote_minutes", "active_trade_minutes"]] = [210, 105]
    raw.loc[(raw.Ticker == "BRK.B") & (raw.TradeDate > "2026-01-01"), "ResearchKey"] = (
        "other:BRK.B"
    )
    result = prepare_daily(raw, cal)
    first = result[(result.ticker == "BRK.B") & (result.date == "2026-01-01")].iloc[0]
    assert first.active_fraction == 0.5
    assert pd.isna(first.target)


def test_membership_does_not_require_future_first_day_observation():
    raw = daily()
    raw = raw[~((raw.Ticker == "A") & (raw.TradeDate == "2026-02-02"))]
    members = monthly_membership(prepare_daily(raw, schedule()), cap=1)
    assert members[members.month == "2026-02"].candidate_id.tolist() == ["unresolved:A"]


def test_freeze_is_exclusive_and_records_hashes(tmp_path):
    source = tmp_path / "data.csv"
    source.write_bytes(b"a\n1\n")
    dest = tmp_path / "frozen"
    receipt = freeze_inputs([source], dest)
    assert receipt["files"][0]["size"] == 4
    assert len(receipt["files"][0]["sha256"]) == 64
    assert (dest / "data.csv").read_bytes() == source.read_bytes()
    with pytest.raises(FileExistsError):
        freeze_inputs([source], dest)
