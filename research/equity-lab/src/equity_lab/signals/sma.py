from __future__ import annotations

import pandas as pd

SIGNAL_NAME = "sma"
DISPLAY_NAME = "Simple Moving Average Cross Signal"
DESCRIPTION = "Binary long-only signal where short SMA is above long SMA."


def generate_sma_signal(
    market_df: pd.DataFrame,
    short_window: int = 20,
    long_window: int = 60,
) -> pd.DataFrame:

    if short_window >= long_window:
        raise ValueError("short_window must be smaller than long_window")

    df = market_df.copy().sort_values(["code", "date"]).reset_index(drop=True)
    grouped = df.groupby("code", group_keys=False)
    df["sma_short"] = grouped["close"].transform(lambda s: s.rolling(short_window).mean())
    df["sma_long"] = grouped["close"].transform(lambda s: s.rolling(long_window).mean())

    # State signal
    df["signal"] = (df["sma_short"] > df["sma_long"]).astype(int)

    return df
