"""Descriptive same-condition comparisons of saved trend and exposure controls."""

import math
from datetime import date
from statistics import median


def compare_pairs(accounts):
    groups = {}
    for row in accounts:
        if row.get("arm") not in {"trend_weekly", "matched_weekly"}:
            continue
        if (
            type(row.get("fee_bps")) is not int
            or row["fee_bps"] not in (0, 35, 50)
            or type(row.get("delay")) is not int
            or row["delay"] not in (0, 1)
            or row.get("currency", "USDT") != "USDT"
        ):
            raise ValueError("INVALID_PAIR_DIMENSIONS")
        for field in ("window", "end"):
            if date.fromisoformat(row[field]).isoformat() != row[field]:
                raise ValueError("INVALID_PAIR_DATE")
        if row["end"] < row["window"]:
            raise ValueError("INVALID_PAIR_RANGE")
        key = row["window"], row["end"], row["fee_bps"], row["delay"]
        group = groups.setdefault(key, {})
        if row["arm"] in group:
            raise ValueError("DUPLICATE_PAIR_ARM")
        for field in (
            "net_return",
            "mean_post_trade_exposure",
            "max_drawdown",
            "turnover",
        ):
            value = row.get(field)
            if value is not None and (
                type(value) not in (int, float) or not math.isfinite(value)
            ):
                raise ValueError("NONFINITE_PAIR_RESULT")
        group[row["arm"]] = row
    rows = []
    for (window, end, fee, delay), group in sorted(groups.items()):
        a, b = group.get("trend_weekly"), group.get("matched_weekly")
        complete = (
            a is not None
            and b is not None
            and all(
                r.get("net_return") is not None
                and r.get("mean_post_trade_exposure") is not None
                for r in (a, b)
            )
        )
        result = dict(
            window=window,
            end=end,
            fee_bps=fee,
            delay=delay,
            status="completed" if complete else "blocked",
        )
        for field, name in (
            ("net_return", "return"),
            ("mean_post_trade_exposure", "exposure"),
            ("max_drawdown", "drawdown"),
            ("turnover", "turnover"),
        ):
            result[name + "_difference"] = (
                a[field] - b[field]
                if complete and a.get(field) is not None and b.get(field) is not None
                else None
            )
        rows.append(result)
    comparable = [r for r in rows if r["status"] == "completed"]
    return dict(
        schema="competition.crypto_paired_controls.v1",
        currency="USDT",
        requested=len(rows),
        comparable=len(comparable),
        return_wins=sum(r["return_difference"] > 0 for r in comparable),
        median_return_difference=median(r["return_difference"] for r in comparable)
        if comparable
        else None,
        same_volatility_claimed=False,
        causal_alpha_claimed=False,
        rows=rows,
    )
