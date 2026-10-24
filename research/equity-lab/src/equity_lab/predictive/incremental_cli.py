"""Optional fixed incremental-information study CLI."""

import json

from equity_lab.run_guard import digest, supervise

PROTOCOL = "equity.reversal_incremental.20261024.v1"


def main(argv=None):
    args, code = supervise(
        "equity_lab.predictive.incremental_cli", PROTOCOL, 1200, argv
    )
    if code is not None:
        return code
    import exchange_calendars as xcals
    import pandas as pd

    from .data import prepare_daily
    from .incremental import run_incremental, _write

    before = digest(args.input)
    raw = pd.read_parquet(args.input)
    start, end = (
        pd.to_datetime(raw.TradeDate).min(),
        pd.to_datetime(raw.TradeDate).max(),
    )
    calendar = xcals.get_calendar("XNYS", start=start, end=end)
    schedule = calendar.schedule.loc[
        str(start.date()) : str(end.date()), ["open", "close"]
    ]
    frame = prepare_daily(raw, schedule)
    report = run_incremental(
        frame, schedule.index.strftime("%Y-%m-%d").tolist()[:-1], args.output
    )
    report.update(
        source_sha256=before,
        source_unchanged=digest(args.input) == before,
        protocol=PROTOCOL,
        calendar_version=xcals.__version__,
    )
    if not report["source_unchanged"]:
        report["status"] = "source_changed"
    _write(args.output / "report.json", report)
    print(
        json.dumps({k: report[k] for k in ("status", "fit_attempts", "pnl_available")})
    )
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
