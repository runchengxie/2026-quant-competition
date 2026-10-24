"""Reserved fixed weekly batch using only previously frozen daily windows."""

import json
import time

from crypto_mm.run_guard import digest, supervise
from .weekly import evaluate_weekly
from .study_accounting import validate_prices

PROTOCOL = "crypto.weekly_cost.20261024.v1"


def main(argv=None):
    args, code = supervise("crypto_mm.daily.weekly_cli", PROTOCOL, 600, argv)
    if code is not None:
        return code
    started = time.monotonic()
    before = digest(args.input)
    batch = json.loads(args.input.read_text(encoding="utf-8"))
    if (
        set(batch) != {"schema", "windows"}
        or batch["schema"] != "crypto.weekly_input.v1"
        or len(batch["windows"]) != 12
    ):
        raise ValueError("Invalid frozen weekly batch")
    seen = set()
    for window in batch["windows"]:
        if (
            set(window) != {"window_id", "bars", "parent_sha256"}
            or window["window_id"] in seen
        ):
            raise ValueError("Invalid weekly window")
        seen.add(window["window_id"])
        validate_prices(window["bars"])
        if len(window["bars"]["dates"]) != 342 or len(window["bars"]["close"]) != 8:
            raise ValueError("Invalid weekly fixed scope")
    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        "schema": "crypto.weekly_private.v1",
        "status": "running",
        "protocol": PROTOCOL,
        "source_sha256": before,
        "retrospective": True,
        "quote_currency": "USDT",
        "jobs": [],
    }
    attempts = args.output / "attempts.jsonl"
    with attempts.open("x", encoding="utf-8"):
        pass
    for window in batch["windows"]:
        for fee in (35, 50):
            if time.monotonic() - started >= 600:
                raise RuntimeError("Weekly time budget exhausted")
            with attempts.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {
                            "window_id": window["window_id"],
                            "fee_bps": fee,
                            "net_accounts": 5,
                            "gross_accounts": 5,
                        }
                    )
                    + "\n"
                )
                stream.flush()
            results = evaluate_weekly(window["bars"], fee)
            for arm, result in results.items():
                filename = f"{window['window_id']}-{fee}-{arm}.json"
                (args.output / filename).write_text(
                    json.dumps(result, allow_nan=False), encoding="utf-8"
                )
                report["jobs"].append(
                    {
                        "window_id": window["window_id"],
                        "start": window["bars"]["dates"][252],
                        "end": window["bars"]["dates"][-1],
                        "fee_bps": fee,
                        "arm": arm,
                        "metrics": result["metrics"],
                        "actual_rebalances": result["actual_rebalances"],
                        "scheduled_rebalances": result["scheduled_rebalances"],
                        "artifact": filename,
                    }
                )
            (args.output / "report.json").write_text(
                json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
            )
    report.update(
        status="completed",
        source_unchanged=digest(args.input) == before,
        net_simulations=len(report["jobs"]),
        gross_simulations=len(report["jobs"]),
    )
    if not report["source_unchanged"]:
        report["status"] = "source_changed"
    (args.output / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {"status": report["status"], "net_simulations": report["net_simulations"]}
        )
    )
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
