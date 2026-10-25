"""Reserved multi-session ML research, separate from accepted trading PnL."""

import json

from equity_lab.run_guard import digest, supervise

PROTOCOL = "equity.low_turnover_ml.20261025.v1"


def main(argv=None):
    args, code = supervise("equity_lab.predictive.holding_cli", PROTOCOL, 2400, argv)
    if code is not None:
        return code
    import pandas as pd
    import exchange_calendars as xcals
    from .holding import run_holding

    before = digest(args.input)
    raw = pd.read_parquet(args.input)
    start, end = pd.to_datetime(raw.TradeDate).agg(["min", "max"])
    calendar = xcals.get_calendar("XNYS", start=start, end=end)
    schedule = calendar.schedule.loc[
        str(start.date()) : str(end.date()), ["open", "close"]
    ]
    report = run_holding(raw, schedule, args.output)
    if digest(args.input) != before:
        raise ValueError("HOLDING_INPUT_CHANGED")
    report.update(
        protocol=PROTOCOL,
        input_sha256=before,
        source_unchanged=True,
        calendar_version=xcals.__version__,
    )
    (args.output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            dict(
                status=report["status"],
                fit_attempts=report["fit_attempts"],
                accounts=len(report["accounts"]),
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
