"""Reserved 288-cell daily-price stress comparison with no live execution."""

import json
import time

from crypto_mm.run_guard import digest, supervise
from .comparison import ARMS, FEES, DELAYS, evaluate_comparison
from .weekly_cli import validate_batch

PROTOCOL = "crypto.strategy_cost_delay.20261025.v1"


def main(argv=None):
    args, code = supervise("crypto_mm.daily.comparison_cli", PROTOCOL, 600, argv)
    if code is not None:
        return code
    started = time.monotonic()
    before = digest(args.input)
    batch = validate_batch(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(
        schema="crypto.strategy_comparison.v1",
        status="running",
        protocol=PROTOCOL,
        source_sha256=before,
        retrospective=True,
        quote_currency="USDT",
        accounts=[],
    )
    attempts = args.output / "attempts.jsonl"
    with attempts.open("x", encoding="utf-8"):
        pass
    for window in batch["windows"]:
        for arm in ARMS:
            for fee in FEES:
                for delay in DELAYS:
                    if time.monotonic() - started >= 600:
                        raise RuntimeError("COMPARISON_TIME_BUDGET")
                    identity = dict(
                        window=window["window_id"], arm=arm, fee_bps=fee, delay=delay
                    )
                    with attempts.open("a", encoding="utf-8") as stream:
                        stream.write(
                            json.dumps(
                                identity | dict(net_accounts=1, gross_accounts=1)
                            )
                            + "\n"
                        )
                    result = evaluate_comparison(window["bars"], arm, fee, delay)
                    name = f"{window['window_id']}-{arm}-{fee}-{delay}.json"
                    with (args.output / name).open("x", encoding="utf-8") as stream:
                        stream.write(json.dumps(result, allow_nan=False))
                    report["accounts"].append(
                        identity
                        | dict(
                            end=window["bars"]["dates"][-1],
                            status="completed",
                            path=name,
                            requested_dates=90,
                            valid_dates=len(result["net"]["periods"]),
                            metrics=result["metrics"],
                        )
                    )
    if time.monotonic() - started >= 600 or digest(args.input) != before:
        raise RuntimeError("COMPARISON_BUDGET_OR_INPUT_CHANGED")
    report.update(status="completed", source_unchanged=True)
    with (args.output / "report.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps(dict(status="completed", accounts=len(report["accounts"]))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
