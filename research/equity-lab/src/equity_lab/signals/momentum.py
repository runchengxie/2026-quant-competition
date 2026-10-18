from __future__ import annotations

import pandas as pd

SIGNAL_NAME = "momentum"
DISPLAY_NAME = "Cross-Sectional Momentum Signal"
DESCRIPTION = "Long-only signal where rolling momentum is positive over a configurable lookback window."


def generate_momentum_signal(
    market_df: pd.DataFrame,
    lookback_days: int = 20,
    min_momentum: float = 0.0,
) -> pd.DataFrame:
    if lookback_days <= 0:
        raise ValueError("lookback_days must be positive")

    df = market_df.copy().sort_values(["code", "date"]).reset_index(drop=True)
    grouped = df.groupby("code", group_keys=False)
    df["momentum_return"] = grouped["close"].transform(
        lambda s: s / s.shift(lookback_days) - 1.0
    )
    df["signal"] = (df["momentum_return"] > float(min_momentum)).astype(int)
    return df
