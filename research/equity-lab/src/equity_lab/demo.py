"""Create fictional daily bars without downloading market data."""

import json
from pathlib import Path

import pandas as pd

from .data.market_data import MarketDataPaths, save_bars


def build_demo_data(root: Path) -> tuple[Path, ...]:
    market = root / "artifacts/data/processed/market"
    manifest = root / "demo-manifest.json"
    if manifest.exists() or (market.exists() and any(market.iterdir())):
        raise FileExistsError("Demo destination already contains data")
    dates = pd.bdate_range("2026-01-01", periods=90)
    paths = []
    for index, code in enumerate(["HK.DEMO_A", "HK.DEMO_B"]):
        close = pd.Series([100 + index * 20 + day * 0.1 + (day % 9) * 0.2
                           for day in range(len(dates))])
        frame = pd.DataFrame({"date": dates, "code": code, "open": close - 0.2,
                              "high": close + 0.5, "low": close - 0.5,
                              "close": close, "volume": 1000})
        path = MarketDataPaths(market).symbol_file(code)
        save_bars(frame, path)
        paths.append(path)
    manifest.write_text(json.dumps({"synthetic": True,
                                    "purpose": "software demonstration only",
                                    "files": [str(p.relative_to(root)) for p in paths]}, indent=2),
                        encoding="utf-8")
    return tuple(paths)
