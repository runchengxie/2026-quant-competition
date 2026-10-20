"""Publish only documented scalar aggregates, never reproduction locators."""

import json
import math
import re
from datetime import date

RESULT_FIELDS = (
    "strategy",
    "net_return",
    "gross_return",
    "max_drawdown",
    "sharpe",
    "turnover",
    "mean_exposure",
    "start",
    "end",
    "quote_currency",
    "fee_bps",
    "products",
    "universe_status",
    "periods_per_year",
)


def public_snapshot(aggregate: dict) -> dict:
    results = []
    for result in aggregate["daily_results"]:
        row = {key: result[key] for key in RESULT_FIELDS}
        if (
            row["strategy"] not in {"equal_weight", "momentum_63d"}
            or row["quote_currency"] != "USDT"
        ):
            raise ValueError("INVALID_PUBLIC_RESULT_IDENTITY")
        if row["universe_status"] not in {"fixed_current", "point_in_time"}:
            raise ValueError("INVALID_PUBLIC_UNIVERSE")
        if not all(
            isinstance(p, str) and re.fullmatch(r"[A-Z0-9]+USDT", p)
            for p in row["products"]
        ):
            raise ValueError("INVALID_PUBLIC_PRODUCTS")
        for key in (
            "net_return",
            "gross_return",
            "max_drawdown",
            "sharpe",
            "turnover",
            "mean_exposure",
            "fee_bps",
        ):
            if row[key] is not None and (
                type(row[key]) not in {int, float} or not math.isfinite(row[key])
            ):
                raise ValueError("NONFINITE_PUBLIC_METRIC")
        for key in ("start", "end"):
            date.fromisoformat(row[key])
        if row["periods_per_year"] != 365:
            raise ValueError("INVALID_ANNUALIZATION")
        results.append(row)
    coverage = []
    for item in aggregate["coverage"]:
        row = {
            key: item[key]
            for key in (
                "source",
                "status",
                "products",
                "start",
                "end",
                "rows",
                "universe_status",
            )
        }
        if row["source"] != "binance_spot" or row["status"] not in {
            "acquired",
            "partial",
            "blocked",
        }:
            raise ValueError("INVALID_PUBLIC_COVERAGE")
        if not all(re.fullmatch(r"[A-Z0-9]+USDT", p) for p in row["products"]):
            raise ValueError("INVALID_PUBLIC_PRODUCTS")
        if (
            type(row["rows"]) is not int
            or row["rows"] < 0
            or row["universe_status"] not in {"fixed_current", "point_in_time"}
        ):
            raise ValueError("INVALID_PUBLIC_COVERAGE")
        date.fromisoformat(row["start"])
        date.fromisoformat(row["end"])
        coverage.append(row)
    equity = []
    for result in aggregate.get("equity_results", []):
        fields = (
            "market",
            "strategy",
            "fold",
            "status",
            "start",
            "end",
            "universe_count",
            "cost_bps",
            "quote_currency",
            "net_return",
            "sharpe",
            "max_drawdown",
            "turnover",
            "mean_exposure",
            "sessions",
        )
        row = {key: result.get(key) for key in fields}
        if (
            row["market"] not in {"US", "HK"}
            or row["strategy"] not in {"equal_weight", "momentum_20d", "sma_cross"}
            or row["quote_currency"] != ("USD" if row["market"] == "US" else "HKD")
            or row["status"] not in {"completed", "failed", "blocked"}
        ):
            raise ValueError("INVALID_PUBLIC_EQUITY_IDENTITY")
        for key in ("start", "end"):
            date.fromisoformat(row[key])
        for key in (
            "fold",
            "universe_count",
            "cost_bps",
            "net_return",
            "sharpe",
            "max_drawdown",
            "turnover",
            "mean_exposure",
            "sessions",
        ):
            if row[key] is not None and (
                type(row[key]) not in {int, float} or not math.isfinite(row[key])
            ):
                raise ValueError("INVALID_PUBLIC_EQUITY_METRIC")
        equity.append(row)
    maker = []
    for result in aggregate.get("maker_results", []):
        if result["strategy_id"] not in {"B0", "B1", "B2", "B3"} or result[
            "scenario"
        ] not in {"baseline", "fee_1bps", "latency_300ms"}:
            raise ValueError("INVALID_PUBLIC_MAKER_IDENTITY")
        for day in result["days"]:
            date.fromisoformat(day)
        metrics = {key: result["metrics"][key] for key in ("total_pnl", "fill_count")}
        if any(
            type(v) not in {float, int} or not math.isfinite(v)
            for v in metrics.values()
        ):
            raise ValueError("INVALID_PUBLIC_MAKER_METRIC")
        maker.append(
            {
                "strategy": result["strategy_id"],
                "scenario": result["scenario"],
                "days": result["days"],
                "quote_currency": None,
                "evidence": "archived_unverified_venue_product",
                **metrics,
            }
        )
    blockers = aggregate["blockers"]
    if not all(re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code) for code in blockers):
        raise ValueError("INVALID_PUBLIC_BLOCKER")
    value = {
        "schema": "competition.public_strategy_expansion.v1",
        "retrospective": True,
        "accepted_research": False,
        "daily_results": results,
        "coverage": coverage,
        "blockers": blockers,
        "equity_results": equity,
        "maker_results": maker,
    }
    json.dumps(value, allow_nan=False)
    return value
