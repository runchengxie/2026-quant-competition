"""Reserved bounded historical score/fee comparison, never formal trading PnL."""

import json

from equity_lab.run_guard import digest, supervise

PROTOCOL = "equity.strategy_cost_delay.20261025.v1"


def main(argv=None):
    args, code = supervise("equity_lab.predictive.comparison_cli", PROTOCOL, 1200, argv)
    if code is not None:
        return code
    import exchange_calendars as xcals
    import pandas as pd

    from equity_lab.data.comparison_quality import audit_daily
    from .data import prepare_daily
    from .comparison import run_comparison

    before = digest(args.input)
    raw = pd.read_parquet(args.input)
    start, end = pd.to_datetime(raw.TradeDate).agg(["min", "max"])
    calendar = xcals.get_calendar("XNYS", start=start, end=end)
    schedule = calendar.schedule.loc[
        str(start.date()) : str(end.date()), ["open", "close"]
    ]
    quality = audit_daily(raw, schedule)
    frame = prepare_daily(raw, schedule)
    report = run_comparison(
        frame,
        schedule.index.strftime("%Y-%m-%d").tolist(),
        args.output,
        quality=quality,
    )
    report.update(
        source_sha256=before,
        source_unchanged=digest(args.input) == before,
        protocol=PROTOCOL,
        calendar_version=xcals.__version__,
    )
    if not report["source_unchanged"]:
        raise ValueError("COMPARISON_INPUT_CHANGED")
    (args.output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
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
