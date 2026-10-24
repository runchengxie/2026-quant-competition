"""Explicit optional CLI; never imported by the default equity command."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Bounded retrospective candidate prediction; no trading PnL"
    )
    parser.add_argument(
        "--input", type=Path, required=True, help="Frozen daily_features.parquet"
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="New external result directory"
    )
    parser.add_argument(
        "--mode", required=True, choices=["exploratory_source_candidates"]
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    source = args.input.resolve(strict=True)
    destination = args.output.resolve()
    # Source checkouts, archives and installed wheels have different depths.
    # Discover project boundaries rather than assuming a parent index.
    module = Path(__file__).resolve()
    candidates = [*module.parents, Path.cwd().resolve(), *Path.cwd().resolve().parents]
    boundaries = [
        p
        for p in candidates
        if (p / ".git").exists() or (p / "pyproject.toml").is_file()
    ]
    boundaries.append(module.parent.parent)
    if any(
        destination.is_relative_to(p) for p in boundaries
    ) or destination.is_relative_to(source.parent):
        parser.error("Output must be outside the checkout and source input directory")
    if not args.worker:
        if destination.exists():
            parser.error("Output already exists; uncertain runs are not retried")
        env = {
            **os.environ,
            "OMP_NUM_THREADS": "2",
            "OPENBLAS_NUM_THREADS": "2",
            "MKL_NUM_THREADS": "2",
        }
        command = [
            sys.executable,
            "-m",
            "equity_lab.predictive.cli",
            "--input",
            str(source),
            "--output",
            str(destination),
            "--mode",
            args.mode,
            "--worker",
        ]
        try:
            return subprocess.run(command, timeout=1200, env=env).returncode
        except subprocess.TimeoutExpired:
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "timeout.json").write_text(
                json.dumps({"schema_version": 1, "status": "timeout", "seconds": 1200}),
                encoding="utf-8",
            )
            return 2
    import exchange_calendars as xcals
    import pandas as pd

    from .data import prepare_daily, sha256
    from .protocol import run_pilot

    digest = sha256(source)
    raw = pd.read_parquet(source)
    start, end = (
        pd.to_datetime(raw.TradeDate).min(),
        pd.to_datetime(raw.TradeDate).max(),
    )
    calendar = xcals.get_calendar("XNYS", start=start, end=end)
    schedule = calendar.schedule.loc[
        str(start.date()) : str(end.date()), ["open", "close"]
    ]
    frame = prepare_daily(raw, schedule)
    # Last feature date must have its next exchange session inside the source range.
    sessions = schedule.index.strftime("%Y-%m-%d").tolist()[:-1]
    report = run_pilot(frame, sessions, destination, args.mode)
    report["source_sha256"] = digest
    report["calendar"] = {
        "name": "XNYS",
        "version": xcals.__version__,
        "source_start": str(start.date()),
        "source_end": str(end.date()),
    }
    report["source_unchanged"] = sha256(source) == digest
    if not report["source_unchanged"]:
        report["status"] = "source_changed"
    (destination / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "status",
                    "fit_attempts",
                    "source_candidate_count",
                    "formal_common_stock_ready",
                ]
            }
        )
    )
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
