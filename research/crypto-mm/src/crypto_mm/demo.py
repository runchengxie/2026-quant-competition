"""Generate deterministic fictional input files without downloading market data."""

from datetime import datetime, timedelta
import json
from pathlib import Path

import polars as pl

from crypto_mm.config import DATA_ROOT, EXPECTED_DATES


def build_demo_data(raw_root: Path) -> tuple[Path, ...]:
    """Create a small demo, refusing to replace an existing nonempty dataset."""
    if raw_root.exists() and any(raw_root.iterdir()):
        raise FileExistsError(f"Refusing to overwrite existing data: {raw_root}")
    manifest = raw_root.parent / "demo-manifest.json"
    if manifest.exists():
        raise FileExistsError(f"Refusing to overwrite existing metadata: {manifest}")
    paths = []
    for day in EXPECTED_DATES:
        times = [datetime.fromisoformat(day) + timedelta(seconds=s) for s in range(121)]
        mids = [100.0 + 0.1 * ((s // 5) % 7) for s in range(121)]
        book = {"datetime": pl.Series(times, dtype=pl.Datetime("ns"))}
        for level in range(1, 21):
            book[f"bid_price_{level}"] = [round(m - level * 0.1, 1) for m in mids]
            book[f"ask_price_{level}"] = [round(m + level * 0.1, 1) for m in mids]
            book[f"bid_qty_{level}"] = [1.0] * len(times)
            book[f"ask_qty_{level}"] = [1.0] * len(times)
        frames = {
            "orderbook": pl.DataFrame(book),
            "trades": pl.DataFrame({
                "datetime": pl.Series(times, dtype=pl.Datetime("ns")),
                "price": [round(m + (0.1 if i % 2 else -0.1), 1) for i, m in enumerate(mids)],
                "size": [2.0] * len(times),
                "is_maker_ask": [i % 2 for i in range(len(times))],
            }),
            "fundings": pl.DataFrame({
                "datetime": pl.Series(times, dtype=pl.Datetime("ns")),
                "funding_rate": [0.0] * len(times),
            }),
        }
        for dataset, frame in frames.items():
            path = raw_root / dataset / f"{day}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.write_parquet(path)
            paths.append(path)
    manifest.write_text(json.dumps({
        "synthetic": True, "purpose": "software demonstration only",
        "files": [p.relative_to(raw_root).as_posix() for p in paths],
    }, indent=2), encoding="utf-8")
    return tuple(paths)


def main() -> None:
    paths = build_demo_data(DATA_ROOT)
    print(f"Created {len(paths)} synthetic demonstration files under {DATA_ROOT}")
    print("These files are fictional and cannot substantiate strategy performance.")


if __name__ == "__main__":
    main()
