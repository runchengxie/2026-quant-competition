from __future__ import annotations

from hashlib import blake2b
from pathlib import Path

import numpy as np
import pandas as pd

from .common import load_universe_file

STRATEGY_NAME = "random_turnover"
DEFAULT_CONFIG_NAME = "random_turnover"
DISPLAY_NAME = "Random Turnover"
DESCRIPTION = "Random baseline with fixed top-N selection each date and stable seeds to mimic turnover controls in benchmarks."
SUPPORTED_MARKETS = ["HK", "US", "CN"]
REQUIRED_CONFIG_KEYS = ["name", "universe", "position_sizing"]
DEFAULT_SIGNAL_KWARGS = {
    "random_seed": 12345,
    "selection_top_n": 8,
}
SIGNAL_NAME = "random_turnover"


def load_universe(path: Path) -> list[str]:
    return load_universe_file(path)


def _seed_from_date(date_key: str, base_seed: int) -> int:
    digest = blake2b(f"{date_key}-{base_seed}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


def build_signal_frame(
    market_df: pd.DataFrame,
    *,
    random_seed: int = 12345,
    selection_top_n: int = 8,
    **_kwargs: object,
) -> pd.DataFrame:
    df = market_df.copy().sort_values(["date", "code"]).reset_index(drop=True)
    if df.empty:
        return df

    n = max(int(selection_top_n), 0)
    selected = pd.Series(False, index=df.index)
    for date, group in df.groupby("date", sort=True):
        date_key = str(pd.Timestamp(str(date)).date())
        if len(group) <= n or n <= 0:
            keep = group.index
        else:
            rng = np.random.default_rng(_seed_from_date(date_key, int(random_seed)))
            keep = np.array(group.index.to_numpy())
            chosen = np.sort(rng.choice(keep, size=n, replace=False))
            keep = group.index[np.isin(group.index.to_numpy(), chosen)]
        selected.loc[keep] = True

    df["signal"] = selected.astype(int)
    df["weight_score"] = 0.0
    df.loc[selected, "weight_score"] = 1.0
    return df
