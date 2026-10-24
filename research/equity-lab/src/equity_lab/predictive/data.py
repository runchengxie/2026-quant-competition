"""Strict session alignment and immutable small-input receipts."""

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

FEATURES = [
    "session_return",
    "range_fraction",
    "relative_dollar_volume",
    "median_spread",
    "quote_fraction",
    "active_fraction",
]


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def freeze_inputs(paths, destination):
    paths = [Path(p).resolve(strict=True) for p in paths]
    if len({p.name for p in paths}) != len(paths):
        raise ValueError("Duplicate input filenames")
    before = [(p, p.stat().st_size, sha256(p)) for p in paths]
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    files = []
    for path, size, digest in before:
        target = destination / path.name
        shutil.copyfile(path, target)
        if sha256(target) != digest or sha256(path) != digest:
            raise ValueError("Source changed while freezing")
        files.append({"name": path.name, "size": size, "sha256": digest})
    receipt = {"schema_version": 1, "files": files}
    (destination / "input-receipt.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    return receipt


def prepare_daily(frame, schedule):
    cal = schedule.copy()
    cal.index = pd.DatetimeIndex(cal.index).tz_localize(None).normalize()
    if cal.index.has_duplicates or not cal.index.is_monotonic_increasing:
        raise ValueError("Invalid calendar")
    source = frame.copy()
    source["date"] = pd.to_datetime(source.TradeDate).dt.normalize()
    source["candidate_id"] = source.ResearchKey.astype(str)
    source["ticker"] = source.Ticker.astype(str)
    if source[["candidate_id", "date"]].duplicated().any():
        raise ValueError("Duplicate candidate/session")
    if not source.date.isin(cal.index).all():
        raise ValueError("Source contains non-session dates")
    if source.candidate_id.str.strip().isin(["", "nan", "None"]).any():
        raise ValueError("Missing candidate identity")
    numeric = [
        "open_price",
        "close_price",
        "high_price",
        "low_price",
        "dollar_volume",
        "median_spread",
        "valid_quote_minutes",
        "active_trade_minutes",
    ]
    for name in numeric:
        source[name] = pd.to_numeric(source[name], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        )
    pieces = []
    for identity, group in source.groupby("candidate_id", sort=True):
        # Reindex to the exchange calendar, never an observed-row calendar.
        grid = group.set_index("date").reindex(cal.index)
        observed = grid.TradeDate.notna()
        duration = (cal["close"] - cal["open"]).dt.total_seconds() / 60
        valid = (
            grid[["open_price", "close_price", "high_price", "low_price"]]
            .notna()
            .all(axis=1)
            & (grid.low_price > 0)
            & (grid.high_price >= grid[["open_price", "close_price"]].max(axis=1))
            & (grid.low_price <= grid[["open_price", "close_price"]].min(axis=1))
        )
        grid["price_valid"] = valid
        grid["session_return"] = (grid.close_price / grid.open_price - 1).where(valid)
        grid["range_fraction"] = (
            (grid.high_price - grid.low_price) / grid.open_price
        ).where(valid)
        volume = grid.dollar_volume.where(grid.dollar_volume >= 0)
        grid["prior_dollar_volume"] = volume.shift().rolling(20, min_periods=20).mean()
        grid["prior_close"] = grid.close_price.where(valid).shift()
        grid["relative_dollar_volume"] = volume / grid.prior_dollar_volume.replace(
            0, np.nan
        )
        for output, column in [
            ("quote_fraction", "valid_quote_minutes"),
            ("active_fraction", "active_trade_minutes"),
        ]:
            grid[output] = (grid[column] / duration).where(
                grid[column].between(0, duration)
            )
        grid["median_spread"] = grid.median_spread.where(grid.median_spread >= 0)
        grid["target"] = grid.session_return.shift(-1)
        grid["label_reason"] = np.where(
            grid.target.notna(), "observed_next_session", "missing_next_session"
        )
        grid["decision_at"] = cal["close"]
        grid["label_end"] = cal["close"].shift(-1)
        grid["date"] = cal.index.strftime("%Y-%m-%d")
        grid["candidate_id"] = identity
        grid["formal_common_stock_ready"] = (
            False  # No complete dated type/action certificate supplied.
        )
        pieces.append(grid.loc[observed])
    if not pieces:
        raise ValueError("Empty source")
    result = (
        pd.concat(pieces, ignore_index=True)
        .sort_values(["date", "candidate_id"])
        .reset_index(drop=True)
    )
    result.attrs["sessions"] = cal.index.strftime("%Y-%m-%d").tolist()
    return result


def monthly_membership(frame, cap=500):
    if not isinstance(cap, int) or not 1 <= cap <= 500:
        raise ValueError("Candidate cap must be 1..500")
    rows = []
    sessions = frame.attrs.get("sessions")
    if not sessions:
        raise ValueError("Explicit exchange calendar required for membership")
    for month in sorted({d[:7] for d in sessions}):
        first = next(i for i, d in enumerate(sessions) if d.startswith(month))
        if first < 20:
            continue
        prior = sessions[first - 20 : first]
        history = frame[frame.date.isin(prior)]
        eligible = []
        for identity, group in history.groupby("candidate_id", sort=True):
            group = group.sort_values("date")
            volume = group.dollar_volume
            if len(group) != 20 or not volume.notna().all() or not (volume >= 0).all():
                continue
            last = group.iloc[-1]
            mean = float(volume.mean())
            if last.price_valid and last.close_price >= 5 and mean >= 10_000_000:
                eligible.append(
                    {
                        "month": month,
                        "candidate_id": identity,
                        "ticker": last.ticker,
                        "mean_dollar_volume": mean,
                        "formal_common_stock_ready": False,
                    }
                )
        rows.extend(
            sorted(
                eligible, key=lambda r: (-r["mean_dollar_volume"], r["candidate_id"])
            )[:cap]
        )
    return pd.DataFrame(
        rows,
        columns=[
            "month",
            "candidate_id",
            "ticker",
            "mean_dollar_volume",
            "formal_common_stock_ready",
        ],
    )
