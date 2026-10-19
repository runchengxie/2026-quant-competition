"""Compare retained legacy decisions with a separately verified owner bundle.

Root imports no research/provider package. The optional Python environment verifies its
own installed provider and bundle before returning a strictly allowlisted projection.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

PIN = "28a32ba707ad72d1eb68cde5075663e1b3819ac7"
PROVIDER = {"repository": "quant-platform", "commit": PIN}
CLOCK_FIELDS = set(
    "schema_version timezone information_cutoff_at signal_at decision_at valuation_at timing_policy_id trading_calendar_ref earliest_order_at execution_window_start_at execution_window_end_at".split()
)
OWNER_FIELDS = set(
    "schema_version status provider market synthetic input_fingerprint upstream_input_fingerprint config_fingerprint schedule_fingerprint manifest_fingerprint initial_cash_usd final_nav_usd final_cash_usd final_positions_usd total_costs_usd traded_notional_usd sizing_mode cost_assumptions return_basis orders_submitted observations transactions order_lifecycle".split()
)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _fields(value, keys):
    if not isinstance(value, dict) or set(value) != set(
        keys.split() if isinstance(keys, str) else keys
    ):
        raise ValueError("INVALID_FIELDS")


def _sha(value):
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ValueError("INVALID_FINGERPRINT")


def _money(value):
    if (
        not isinstance(value, str)
        or re.fullmatch(r"-?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)", value) is None
    ):
        raise ValueError("INVALID_DECIMAL")
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("INVALID_DECIMAL")
    return result


def _text_decimal(value):
    value = format(value, "f")
    return value.rstrip("0").rstrip(".") if "." in value else value


def _time(value):
    if (
        not isinstance(value, str)
        or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value
        )
        is None
    ):
        raise ValueError("INVALID_UTC_CLOCK")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _legacy(value):
    _fields(
        value,
        "schema_version producer strategy_id market frequency synthetic input_fingerprint legacy_config legacy_config_fingerprint decisions legacy",
    )
    if (
        value["schema_version"] != "competition.legacy_decisions.v1"
        or value["market"] not in {"HK", "US"}
        or type(value["synthetic"]) is not bool
    ):
        raise ValueError("INVALID_LEGACY_METADATA")
    _sha(value["input_fingerprint"])
    _sha(value["legacy_config_fingerprint"])
    config = value["legacy_config"]
    if (
        not isinstance(config, dict)
        or digest(config) != value["legacy_config_fingerprint"]
    ):
        raise ValueError("LEGACY_CONFIG_MISMATCH")
    if value["producer"] == "root-monthly":
        if (
            value["frequency"] != "monthly"
            or value["strategy_id"] not in {"pure_momentum", "momentum_volatility"}
            or config.get("mode") != value["strategy_id"]
        ):
            raise ValueError("UNSUPPORTED_LEGACY_PROFILE")
        commission = Decimal(str(config["commission_bps"]))
        basis = "monthly_constant_weight_price_proxy"
    elif value["producer"] == "equity-lab":
        if value["frequency"] != "daily" or value["strategy_id"] not in {
            "equal_weight",
            "momentum_20d",
        }:
            raise ValueError("UNSUPPORTED_LEGACY_PROFILE")
        commission = sum(
            (
                Decimal(str(config[k]))
                for k in ("commission_bps", "regulation_bps", "sec_fee_bps")
            ),
            Decimal(0),
        )
        basis = "lagged_fractional_weight_price_proxy"
    else:
        raise ValueError("UNSUPPORTED_LEGACY_PROFILE")
    summary = value["legacy"]
    _fields(
        summary,
        "initial_cash final_nav observations commission_bps slippage_bps turnover_basis return_basis cash_model",
    )
    if (
        summary["return_basis"] != basis
        or summary["turnover_basis"] != "sum_absolute_target_weight_changes"
        or summary["cash_model"] != "residual_weight_without_fx"
    ):
        raise ValueError("UNSUPPORTED_LEGACY_MODEL")
    if (
        type(summary["observations"]) is not int
        or summary["observations"] < 1
        or _money(summary["initial_cash"]) <= 0
    ):
        raise ValueError("INVALID_LEGACY_SUMMARY")
    _money(summary["final_nav"])
    if _money(summary["commission_bps"]) != commission or _money(
        summary["slippage_bps"]
    ) != Decimal(str(config["slippage_bps"])):
        raise ValueError("LEGACY_COST_MISMATCH")
    if not isinstance(value["decisions"], list):
        raise ValueError("INVALID_DECISIONS")
    previous = None
    for record in value["decisions"]:
        _fields(record, "source_date execution_date weights")
        for key in ("source_date", "execution_date"):
            if (
                not isinstance(record[key], str)
                or re.fullmatch(r"\d{4}-\d{2}-\d{2}", record[key]) is None
            ):
                raise ValueError("INVALID_SESSION_DATE")
            datetime.strptime(record[key], "%Y-%m-%d")
        if record["source_date"] >= record["execution_date"] or (
            previous is not None and record["execution_date"] <= previous
        ):
            raise ValueError("UNALIGNED_DECISION_DATES")
        previous = record["execution_date"]
        if not isinstance(record["weights"], dict):
            raise ValueError("INVALID_WEIGHTS")
        total = Decimal(0)
        for code, weight in record["weights"].items():
            if not isinstance(code, str) or not code.startswith(value["market"] + "."):
                raise ValueError("INSTRUMENT_MARKET_MISMATCH")
            amount = _money(weight)
            if amount < 0:
                raise ValueError("UNSUPPORTED_SHORT_WEIGHT")
            total += amount
        if total > 1:
            raise ValueError("EXCESS_GROSS_WEIGHT")


def bind_clocks(legacy, clock_map):
    _legacy(legacy)
    if clock_map is None:
        raise ValueError("CLOCK_METADATA_REQUIRED")
    _fields(
        clock_map,
        "schema_version input_fingerprint legacy_config_fingerprint decisions",
    )
    if (
        clock_map["schema_version"] != "competition.decision_clocks.v1"
        or clock_map["input_fingerprint"] != legacy["input_fingerprint"]
        or clock_map["legacy_config_fingerprint"] != legacy["legacy_config_fingerprint"]
    ):
        raise ValueError("CLOCK_BINDING_MISMATCH")
    rows = clock_map["decisions"]
    if not isinstance(rows, dict) or set(rows) != {
        r["execution_date"] for r in legacy["decisions"]
    }:
        raise ValueError("CLOCK_DATE_MISMATCH")
    result = []
    for record in legacy["decisions"]:
        sidecar = rows[record["execution_date"]]
        _fields(sidecar, "source_date clock execution_times")
        if sidecar["source_date"] != record["source_date"]:
            raise ValueError("CLOCK_SOURCE_DATE_MISMATCH")
        clock = sidecar["clock"]
        _fields(clock, CLOCK_FIELDS)
        if (
            clock["schema_version"] != "research.clock.v1"
            or clock["timezone"] != "UTC"
            or not all(
                isinstance(clock[k], str) and clock[k]
                for k in ("timing_policy_id", "trading_calendar_ref")
            )
        ):
            raise ValueError("INVALID_CLOCK_METADATA")
        ordered = [
            _time(clock[k])
            for k in (
                "information_cutoff_at",
                "signal_at",
                "decision_at",
                "earliest_order_at",
                "execution_window_start_at",
                "execution_window_end_at",
                "valuation_at",
            )
        ]
        if (
            ordered != sorted(ordered)
            or ordered[0].date().isoformat() != record["source_date"]
        ):
            raise ValueError("NONCAUSAL_CLOCK")
        executions = sidecar["execution_times"]
        if not isinstance(executions, dict) or set(executions) != set(
            record["weights"]
        ):
            raise ValueError("EXECUTION_SYMBOL_MISMATCH")
        for timestamp in executions.values():
            parsed = _time(timestamp)
            if (
                not ordered[4] <= parsed <= ordered[5]
                or parsed.date().isoformat() != record["execution_date"]
            ):
                raise ValueError("NONCAUSAL_EXECUTION")
        result.append(
            {
                "decision_id": legacy["strategy_id"] + "-" + record["execution_date"],
                "clock": dict(clock),
                "weights": {
                    code: _text_decimal(_money(weight))
                    for code, weight in record["weights"].items()
                },
                "execution_times": dict(executions),
            }
        )
    return result


def monthly_export(
    history, benchmark, config, *, market, synthetic, input_fingerprint, initial_cash
):
    from strategies.hk_low_frequency.backtest import run_monthly_backtest

    records = []

    def observe(current, previous, weights):
        records.append(
            {
                "source_date": previous,
                "execution_date": current,
                "weights": {
                    code: _text_decimal(Decimal(str(weights.get(code, 0))))
                    for code in sorted(history)
                },
            }
        )

    result = run_monthly_backtest(history, benchmark, config, decision_observer=observe)
    # Retain the existing engine's floating-point summary, rather than silently
    # recomputing its proxy with a different numerical algorithm.
    nav = str(float(_money(initial_cash)) * (1 + result.metrics.cumulative_return))
    configuration = json.loads(json.dumps(asdict(config), allow_nan=False))
    value = {
        "schema_version": "competition.legacy_decisions.v1",
        "producer": "root-monthly",
        "strategy_id": config.mode,
        "market": market,
        "frequency": "monthly",
        "synthetic": synthetic,
        "input_fingerprint": input_fingerprint,
        "legacy_config": configuration,
        "legacy_config_fingerprint": digest(configuration),
        "decisions": records,
        "legacy": {
            "initial_cash": initial_cash,
            "final_nav": nav,
            "observations": len(result.dates),
            "commission_bps": _text_decimal(Decimal(str(config.commission_bps))),
            "slippage_bps": _text_decimal(Decimal(str(config.slippage_bps))),
            "turnover_basis": "sum_absolute_target_weight_changes",
            "return_basis": "monthly_constant_weight_price_proxy",
            "cash_model": "residual_weight_without_fx",
        },
    }
    _legacy(value)
    return value


def compare_verified(legacy, clock_map, owner):
    decisions = bind_clocks(legacy, clock_map)
    _fields(owner, OWNER_FIELDS)
    if (
        owner["schema_version"] != "competition.accounting_result.v1"
        or owner["status"] != "diagnostic"
        or owner["provider"] != PROVIDER
        or owner["market"] != legacy["market"]
        or type(owner["synthetic"]) is not bool
        or owner["synthetic"] != legacy["synthetic"]
    ):
        raise ValueError("OWNER_METADATA_MISMATCH")
    for key in (
        "input_fingerprint",
        "upstream_input_fingerprint",
        "config_fingerprint",
        "schedule_fingerprint",
        "manifest_fingerprint",
    ):
        _sha(owner[key])
    if owner["upstream_input_fingerprint"] != legacy["input_fingerprint"] or owner[
        "schedule_fingerprint"
    ] != digest(decisions):
        raise ValueError("OWNER_SCHEDULE_OR_INPUT_MISMATCH")
    summary = legacy["legacy"]
    if _money(owner["initial_cash_usd"]) != _money(summary["initial_cash"]):
        raise ValueError("INITIAL_CASH_MISMATCH")
    _fields(owner["cost_assumptions"], "commission_bps slippage_bps fx_cost_bps")
    for key in ("commission_bps", "slippage_bps"):
        if _money(owner["cost_assumptions"][key]) != _money(summary[key]):
            raise ValueError("COST_ASSUMPTION_MISMATCH")
    for key in ("observations", "transactions"):
        if type(owner[key]) is not int or owner[key] < 0:
            raise ValueError("INVALID_OWNER_COUNT")
    if (
        owner["orders_submitted"] is not False
        or owner["order_lifecycle"] is not False
        or owner["return_basis"] != "usd_price_nav"
        or owner["sizing_mode"] not in {"fractional", "integral"}
    ):
        raise ValueError("UNSUPPORTED_OWNER_MODEL")
    for key in (
        "final_nav_usd",
        "final_cash_usd",
        "final_positions_usd",
        "total_costs_usd",
        "traded_notional_usd",
    ):
        _money(owner[key])
    with localcontext() as context:
        context.prec = 50
        delta = _money(owner["final_nav_usd"]) - _money(summary["final_nav"])
    return {
        "schema_version": "competition.accounting_comparison.v1",
        "status": "diagnostic",
        "accepted_research": False,
        "market": legacy["market"],
        "synthetic": legacy["synthetic"],
        "strategy_id": legacy["strategy_id"],
        "frequency": legacy["frequency"],
        "input_fingerprint": legacy["input_fingerprint"],
        "legacy_config_fingerprint": legacy["legacy_config_fingerprint"],
        "schedule_fingerprint": owner["schedule_fingerprint"],
        "models": {"legacy": summary["return_basis"], "owner": owner["return_basis"]},
        "legacy": dict(summary),
        "owner": dict(owner),
        "nav_difference_usd": _text_decimal(delta),
        "model_differences": [
            "cash_share_settlement",
            "quantity_drift",
            "lot_sizing",
            "fx_conversion",
            "turnover_and_cost_basis",
            "execution_timing",
        ],
        "notes": [
            "Legacy values are retained producer diagnostics, not authenticated research evidence.",
            "Equal PnL is not an acceptance condition.",
            "No broker order lifecycle is modeled.",
        ],
    }


def _read(path):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("DUPLICATE_KEY")
            out[key] = value
        return out

    def reject(value):
        raise ValueError("NONFINITE_JSON")

    return json.loads(
        Path(path).read_text(encoding="utf-8-sig"),
        object_pairs_hook=pairs,
        parse_constant=reject,
    )


def verify_and_compare(
    legacy_path, clock_path, *, provider_python, request_path, dataset_root, bundle
):
    legacy = _read(legacy_path)
    clock_map = _read(clock_path)
    bind_clocks(
        legacy, clock_map
    )  # Refuse date-only or mismatched legacy evidence before spawning.
    request = _read(request_path)
    if request.get("provider") != PROVIDER:
        raise ValueError("PROVIDER_PIN_MISMATCH")
    process = subprocess.run(
        [
            str(provider_python),
            "-m",
            "platform_compare.cli",
            "verify",
            "--request",
            str(request_path),
            "--dataset-root",
            str(dataset_root),
            "--bundle",
            str(bundle),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
    )
    if process.returncode != 0:
        raise ValueError("OWNER_VERIFICATION_FAILED")
    owner = json.loads(process.stdout)
    if owner.get("config_fingerprint") != request.get(
        "config_fingerprint"
    ) or owner.get("input_fingerprint") != request.get("input_fingerprint"):
        raise ValueError("REQUEST_BINDING_MISMATCH")
    return compare_verified(legacy, clock_map, owner)


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("INVALID_ARGUMENTS")


def main():
    try:
        parser = SafeParser(description=__doc__)
        for name in (
            "legacy",
            "clocks",
            "provider-python",
            "request",
            "dataset-root",
            "bundle",
        ):
            parser.add_argument("--" + name, required=True, type=Path)
        args = parser.parse_args()
        result = verify_and_compare(
            args.legacy,
            args.clocks,
            provider_python=args.provider_python,
            request_path=args.request,
            dataset_root=args.dataset_root,
            bundle=args.bundle,
        )
        print(json.dumps(result, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        print(
            json.dumps(
                {
                    "schema_version": "competition.accounting_comparison.v1",
                    "status": "blocked",
                    "issue_codes": ["ACCOUNTING_COMPARISON_INVALID"],
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
