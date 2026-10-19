"""Validated, hash-locked loading of the local next-open study inputs."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pandas as pd

ASSET_FILES: Mapping[str, str] = {
    "US_SPY": "US_SPY.csv",
    "HK_2800": "HK_2800.csv",
    "UK_ISF": "UK_ISF.csv",
    "AU_STW": "AU_STW.csv",
    "SG_ES3": "SG_ES3.csv",
}
FX_FILES: Mapping[str, str] = {
    "AUDUSD": "FX_AUDUSD.csv",
    "GBPUSD": "FX_GBPUSD.csv",
    "USDCAD": "FX_USDCAD.csv",
    "USDHKD": "FX_USDHKD.csv",
    "USDSGD": "FX_USDSGD.csv",
}
ASSET_MARKET: Mapping[str, str] = {
    "US_SPY": "US",
    "HK_2800": "HK",
    "UK_ISF": "UK",
    "AU_STW": "AU",
    "SG_ES3": "SG",
}


@dataclass(frozen=True, slots=True)
class NextOpenInputs:
    target_schedule: Mapping[str, Any]
    assets: Mapping[str, pd.DataFrame]
    fx: Mapping[str, pd.DataFrame]
    dataset_manifest: Mapping[str, Any]
    input_hashes: Mapping[str, str]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON input: {path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON input must be an object: {path.name}")
    return value


def _validate_dates(frame: pd.DataFrame, path: Path, cutoff_date: date) -> pd.Series:
    parsed = pd.to_datetime(frame["date"], errors="raise")
    if parsed.isna().any():
        raise ValueError(f"input has an empty date: {path.name}")
    dates = parsed.dt.date
    if dates.duplicated().any():
        raise ValueError(f"input has duplicate dates: {path.name}")
    if (dates > cutoff_date).any():
        raise ValueError(f"input contains a date after the signal cutoff: {path.name}")
    return dates


def _validate_ohlc(frame: pd.DataFrame, path: Path) -> None:
    for column in ("open", "high", "low", "close"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
        if frame[column].isna().any() or not frame[column].map(math.isfinite).all():
            raise ValueError(f"input has non-finite {column}: {path.name}")
        if (frame[column] <= 0).any():
            raise ValueError(f"input has non-positive {column}: {path.name}")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError(f"input has inconsistent high/low OHLC: {path.name}")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError(f"input has inconsistent high/low OHLC: {path.name}")


def _validate_source_evidence(frame: pd.DataFrame, path: Path, *, is_fx: bool) -> None:
    allowed_semantics = "MIDPOINT" if is_fx else "first_regular_hours_trade_open"
    if (
        not frame["price_semantics"]
        .astype(str)
        .str.contains(allowed_semantics, case=False)
        .all()
    ):
        raise ValueError(f"input price semantics mismatch: {path.name}")
    eligible = frame["execution_eligible"].astype(str).str.lower()
    if not eligible.isin(("false", "0")).all():
        raise ValueError(
            f"source input must not claim execution eligibility: {path.name}"
        )


def _load_frame(path: Path, *, cutoff_date: date, is_fx: bool) -> pd.DataFrame:
    if not path.is_file():
        raise ValueError(f"input file does not exist: {path.name}")
    frame = pd.read_csv(path)
    required = {
        "date",
        "open",
        "high",
        "low",
        "close",
        "price_semantics",
        "execution_eligible",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"input missing required columns: {missing}")
    frame = frame.loc[
        :,
        [
            "date",
            "open",
            "high",
            "low",
            "close",
            "price_semantics",
            "execution_eligible",
        ],
    ].copy()
    frame["date"] = _validate_dates(frame, path, cutoff_date)
    _validate_ohlc(frame, path)
    _validate_source_evidence(frame, path, is_fx=is_fx)
    return frame.sort_values("date").reset_index(drop=True)


def _validate_schedule(schedule: dict[str, Any], cutoff_date: date) -> None:
    if schedule.get("schema_version") != "research.target_schedule.v1":
        raise ValueError("unsupported target schedule schema")
    rebalances = schedule.get("rebalances")
    if not isinstance(rebalances, list) or not rebalances:
        raise ValueError("target schedule has no decisions")
    for rebalance in rebalances:
        try:
            signal_date = date.fromisoformat(rebalance["signal_as_of_date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("target schedule has an invalid signal date") from exc
        if signal_date > cutoff_date:
            raise ValueError("target schedule contains a signal after the cutoff")
        targets = rebalance.get("targets")
        if not isinstance(targets, list):
            raise ValueError("target schedule has an invalid targets list")
        ids = [row.get("instrument_id") for row in targets if isinstance(row, dict)]
        if len(ids) != len(targets) or not set(ids) <= set(ASSET_FILES):
            raise ValueError("target schedule contains an unsupported asset universe")


def load_inputs(
    data_root: Path, target_schedule_path: Path, *, cutoff_date: date
) -> NextOpenInputs:
    """Load exact study inputs and verify their manifest-declared hashes."""
    if type(cutoff_date) is not date:
        raise ValueError("cutoff_date must be a plain date")
    data_root = Path(data_root)
    schedule_path = Path(target_schedule_path)
    schedule = _read_json(schedule_path)
    manifest_path = data_root / "dataset-manifest.json"
    manifest = _read_json(manifest_path)
    _validate_schedule(schedule, cutoff_date)
    if manifest.get("execution_eligible") is not False:
        raise ValueError("dataset manifest must remain non-execution-eligible")
    if manifest.get("analysis_cutoff_local_date") != cutoff_date.isoformat():
        raise ValueError("dataset manifest cutoff does not match requested cutoff")
    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, dict):
        raise ValueError("dataset manifest has no file hashes")
    required_asset_files = set(ASSET_FILES.values())
    required_fx_files = set(FX_FILES.values())
    manifest_file_names = set(manifest_files)
    manifest_asset_files = manifest_file_names - required_fx_files
    if manifest_asset_files != required_asset_files:
        raise ValueError(
            "dataset manifest asset universe must contain the five configured ETFs"
        )
    if manifest_file_names.intersection(required_fx_files) != required_fx_files:
        raise ValueError("dataset manifest must contain all five configured FX files")
    if manifest_file_names != required_asset_files | required_fx_files:
        raise ValueError("dataset manifest contains unexpected input files")

    assets = {
        instrument: _load_frame(
            data_root / filename, cutoff_date=cutoff_date, is_fx=False
        )
        for instrument, filename in ASSET_FILES.items()
    }
    fx = {
        pair: _load_frame(data_root / filename, cutoff_date=cutoff_date, is_fx=True)
        for pair, filename in FX_FILES.items()
    }
    hashes: dict[str, str] = {schedule_path.name: _sha256(schedule_path)}
    hashes[manifest_path.name] = _sha256(manifest_path)
    for filename in (*ASSET_FILES.values(), *FX_FILES.values()):
        expected = manifest_files.get(filename, {}).get("sha256")
        actual = _sha256(data_root / filename)
        if not isinstance(expected, str) or actual != expected:
            raise ValueError(f"input hash does not match dataset manifest: {filename}")
        hashes[filename] = actual
    return NextOpenInputs(
        MappingProxyType(schedule),
        MappingProxyType(assets),
        MappingProxyType(fx),
        MappingProxyType(manifest),
        MappingProxyType(hashes),
    )


__all__ = [
    "ASSET_FILES",
    "ASSET_MARKET",
    "FX_FILES",
    "NextOpenInputs",
    "load_inputs",
]
