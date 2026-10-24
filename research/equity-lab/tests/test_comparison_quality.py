"""Quality checks preserve missingness and distinguish no trade from bad trade."""

import pandas as pd
import pytest

from equity_lab.data.comparison_quality import audit_daily, audit_minute


@pytest.fixture
def schedule():
    return pd.DataFrame(
        {
            "open": pd.to_datetime(["2025-11-28T14:30Z"], utc=True),
            "close": pd.to_datetime(["2025-11-28T18:00Z"], utc=True),
        },
        index=pd.to_datetime(["2025-11-28"]),
    )


def test_daily_audit_counts_bad_keys_prices_and_unresolved_identity(schedule):
    rows = pd.DataFrame(
        dict(
            TradeDate=["2025-11-28"] * 2 + ["2025-11-29"],
            Ticker=["DEMO"] * 3,
            ResearchKey=["unresolved:DEMO"] * 3,
            open_price=[10, 10, 10],
            close_price=[11, float("inf"), 11],
            high_price=[12, 12, 9],
            low_price=[9, 9, 9],
            dollar_volume=[100, 100, 100],
        )
    )
    result = audit_daily(rows, schedule)
    assert result["rows"] == 3
    assert result["duplicate_candidate_sessions"] == 1
    assert result["non_session_rows"] == 1
    assert result["invalid_ohlc_rows"] == 2
    assert result["nonfinite_numeric_values"] == 1
    assert result["unresolved_identity_rows"] == 3
    assert result["formal_common_stock_ready"] is False
    assert result["availability_verified"] is False


def minute_rows():
    return pd.DataFrame(
        dict(
            Date=["20251128"] * 3,
            Ticker=["DEMO"] * 3,
            TimeBarStart=["12:58", "12:59", "13:00"],
            AuditSession=["regular"] * 3,
            AuditBarStartUTC=[
                "2025-11-28T17:58Z",
                "2025-11-28T17:59Z",
                "2025-11-28T18:00Z",
            ],
            AuditTotalVolume=["0", "100", "100"],
            FirstTradePrice=["", "10", "10"],
            LastTradePrice=["", "11", "11"],
            HighTradePrice=["", "12", "12"],
            LowTradePrice=["", "9", "9"],
            CloseBidPrice=["10", "11", "10"],
            CloseAskPrice=["10.1", "10", ""],
        )
    )


def test_minute_audit_respects_early_close_and_zero_volume(schedule):
    result = audit_minute(minute_rows(), schedule)
    assert result["rows"] == 3
    assert result["invalid_traded_ohlc_rows"] == 0
    assert result["zero_volume_rows"] == 1
    assert result["regular_rows_outside_session"] == 1
    assert result["crossed_quote_rows"] == 1
    assert result["missing_quote_rows"] == 1


def test_minute_duplicate_and_nonfinite_trade_are_reported(schedule):
    rows = minute_rows()
    rows.loc[1, ["TimeBarStart", "AuditBarStartUTC"]] = rows.loc[
        0, ["TimeBarStart", "AuditBarStartUTC"]
    ]
    rows.loc[1, "LastTradePrice"] = "inf"
    result = audit_minute(rows, schedule)
    assert result["duplicate_minute_keys"] == 1
    assert result["invalid_traded_ohlc_rows"] == 1
    assert result["nonfinite_numeric_values"] == 1


def test_missing_required_columns_stop_audit(schedule):
    with pytest.raises(ValueError):
        audit_daily(pd.DataFrame(), schedule)
    with pytest.raises(ValueError):
        audit_minute(pd.DataFrame(), schedule)
