"""Frozen scientific protocol validation before provider access."""

import re
from pathlib import Path
from .dex_spec import safe_path, validate_dex_spec
from .dex_storage import read_json

SIGNALS = [
    "momentum_24h",
    "momentum_168h",
    "volume_ratio_24h_7d",
    "momentum_volume_24h",
]


def load_factor_protocol(path: Path) -> dict:
    value = read_json(safe_path(path))
    try:
        constants = dict(
            schema="competition.dex_factor_protocol.v1",
            signals=SIGNALS,
            horizons=[6, 24],
            sampling=["all_valid", "non_overlapping"],
            role="retrospective",
            parameter_search=False,
            minimum_overall=30,
            minimum_slice=20,
            slices=3,
            slice_hours=720,
            groups=3,
            minimum_underlyings=9,
            minimum_per_group=3,
            availability="bar_close_proxy_unverified",
        )
        if not isinstance(value, dict) or set(value) != set(constants) | {
            "dataset",
            "manifest_file",
            "source_commit",
            "source_files",
        }:
            raise ValueError
        if any(
            type(value[k]) is not type(v) or value[k] != v for k, v in constants.items()
        ):
            raise ValueError
        manifest = safe_path(value["manifest_file"])
        if not re.fullmatch("[a-f0-9]{40}", value["source_commit"]):
            raise ValueError
        # Reuse the root producer identity validation without opening credentials.
        dataset = value["dataset"]
        expected = {
            "dataset_id",
            "version",
            "source",
            "interval",
            "quote_currency",
            "selection",
            "start",
            "end",
            "assets",
        }
        if set(dataset) != expected:
            raise ValueError
        validate_dex_spec(
            dataset
            | dict(
                schema="competition.dex_dataset_spec.v1",
                credential_file=str(manifest.parent / "unused.env"),
                protocol_file=str(safe_path(path)),
                protocol_sha256="0" * 64,
                budget={
                    "requests": 100,
                    "bytes": 52428800,
                    "seconds": 900,
                    "requests_per_minute": 20,
                },
            )
        )
        files = value["source_files"]
        names = {
            "factors/" + n + ".py"
            for n in ("__init__", "__main__", "inputs", "signals", "metrics", "study")
        }
        if (
            len(files) != 6
            or {f["path"] for f in files} != names
            or any(
                set(f) != {"path", "sha256"}
                or not re.fullmatch("[a-f0-9]{64}", f["sha256"])
                for f in files
            )
        ):
            raise ValueError
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ValueError("INVALID_FACTOR_PROTOCOL") from None
    return value
