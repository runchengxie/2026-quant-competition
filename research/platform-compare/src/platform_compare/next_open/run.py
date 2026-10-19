"""Run the locked global ETF next-open diagnostic experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from research_contracts import ArtifactRef, ResearchClock

from portfolio_backtester.usd_ledger import run_usd_price_replay
from portfolio_backtester.usd_ledger_bundle import write_usd_price_replay_bundle

from .adapter import (
    CALENDAR_PACKAGE,
    CALENDAR_PACKAGE_VERSION,
    MARKET_CALENDARS,
    build_cost_scenarios,
    build_replay_request,
)
from .loader import load_inputs

from platform_compare.contracts import PIN
from platform_compare.owner_adapter import external_output, verify_provider


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_config(path: Path) -> dict[str, Any]:
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("cannot read experiment configuration") from exc
    required = {
        "experiment_id",
        "strategy_id",
        "data_root",
        "target_schedule_path",
        "signal_cutoff",
        "initial_cash_usd",
        "sizing_mode",
        "max_price_age_days",
        "max_fx_age_days",
        "production_eligible",
        "return_basis",
        "reference_cost_bps",
    }
    if not isinstance(config, dict) or not required <= config.keys():
        raise ValueError("experiment configuration is missing required fields")
    if (
        config["production_eligible"] is not False
        or config["return_basis"] != "usd_price_nav"
    ):
        raise ValueError("experiment must remain non-production USD price NAV")
    if config["sizing_mode"] != "fractional":
        raise ValueError("experiment sizing mode must be fractional")
    if config["reference_cost_bps"] != {
        "commission": 5,
        "equity_slippage": 5,
        "fx": 0,
    }:
        raise ValueError(
            "reference cost case must remain the approved 5/5/0 bps lower bound"
        )
    return config


def _input_lock(
    config: dict[str, Any], config_path: Path, inputs: Any, schedule_path: Path
) -> dict[str, Any]:
    return {
        "schema_version": "global_etf_next_open.input_lock.v1",
        "experiment_id": config["experiment_id"],
        "strategy_id": config["strategy_id"],
        "signal_cutoff": config["signal_cutoff"],
        "target_schedule_sha256": inputs.input_hashes[schedule_path.name],
        "dataset_manifest_sha256": inputs.input_hashes["dataset-manifest.json"],
        "source_file_sha256": {
            name: digest
            for name, digest in inputs.input_hashes.items()
            if name not in {schedule_path.name, "dataset-manifest.json"}
        },
        "configuration_sha256": _sha256(config_path),
        "calendar": {
            "package": CALENDAR_PACKAGE,
            "version": CALENDAR_PACKAGE_VERSION,
            "markets": dict(MARKET_CALENDARS),
        },
        "platform_revision": PIN,
        "dataset_id": inputs.dataset_manifest.get("dataset_id"),
        "assumptions": [
            "daily first regular-hours trade open is a modeled reference price",
            "daily close is carried as assumed-date-lag valuation evidence",
            "same-session daily FX midpoint open is assumed and non-executable",
            "USD price NAV excludes dividends and total-return adjustments",
        ],
        "orders_submitted": False,
        "execution_eligible": False,
    }


def _input_refs(inputs: Any) -> list[dict[str, str]]:
    return [
        ArtifactRef(f"ibkr-daily:{name}", digest).to_mapping()
        for name, digest in sorted(inputs.input_hashes.items())
    ]


def _clock(request: Any, result: Any) -> ResearchClock:
    first = request.decisions[0].clock
    daily_times = pd.to_datetime(result.daily["valuation_at"], utc=True)
    execution_starts = [
        decision.clock.execution_window_start_at for decision in request.decisions
    ]
    execution_ends = [
        decision.clock.execution_window_end_at for decision in request.decisions
    ]
    execution_starts = [value for value in execution_starts if value is not None]
    execution_ends = [value for value in execution_ends if value is not None]
    first_execution = min(execution_starts)
    last_execution = max(execution_ends)
    return ResearchClock(
        "UTC",
        first.information_cutoff_at,
        first.signal_at,
        first.decision_at,
        daily_times.max().to_pydatetime(),
        first.timing_policy_id,
        first.trading_calendar_ref,
        first_execution,
        first_execution,
        last_execution,
    )


def _metrics(scenario: Any, result: Any) -> dict[str, Any]:
    daily = result.daily
    nav = pd.to_numeric(daily["nav_usd"], errors="raise")
    peaks = nav.cummax()
    drawdown = nav.div(peaks).sub(1)
    return {
        "scenario_id": scenario.scenario_id,
        "commission_bps": float(scenario.commission_bps),
        "equity_slippage_bps": float(scenario.slippage_bps),
        "fx_cost_bps": float(scenario.fx_cost_bps),
        "cumulative_return": float(result.summary["cumulative_return"]),
        "max_drawdown": float(drawdown.min()),
        "ending_cash_usd": float(daily["cash_usd"].iloc[-1]),
        "ending_positions_usd": float(daily["positions_usd"].iloc[-1]),
        "ending_nav_usd": float(nav.iloc[-1]),
        "cumulative_costs_usd": float(pd.to_numeric(daily["costs_usd"]).sum()),
        "transaction_count": len(result.transactions),
        "orders_submitted": False,
        "execution_eligible": False,
    }


def run_experiment(config_path: Path, output_dir: Path) -> dict[str, Any]:
    """Run all scenarios into a new output directory outside the repository."""
    config_path = Path(config_path).resolve()
    output_dir = external_output(output_dir)
    verify_provider()
    if output_dir.exists():
        raise ValueError("output directory already exists")
    config = _read_config(config_path)
    cutoff = date.fromisoformat(str(config["signal_cutoff"]))
    data_root = Path(config["data_root"]).expanduser().resolve()
    schedule_path = Path(config["target_schedule_path"]).expanduser().resolve()
    inputs = load_inputs(data_root, schedule_path, cutoff_date=cutoff)
    if inputs.target_schedule.get("strategy_id") != config["strategy_id"]:
        raise ValueError(
            "configured strategy_id does not match the frozen target schedule"
        )
    lock = _input_lock(config, config_path, inputs, schedule_path)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent))
    try:
        (stage / "input-lock.json").write_text(
            json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        try:
            first_scenario = build_cost_scenarios()[0]
            base_request = build_replay_request(
                inputs,
                first_scenario,
                initial_cash=Decimal(str(config["initial_cash_usd"])),
                max_price_age=timedelta(days=int(config["max_price_age_days"])),
                max_fx_age=timedelta(days=int(config["max_fx_age_days"])),
            )
        except ValueError as exc:
            (stage / "rejected-events.json").write_text(
                json.dumps([{"event": "input_rejected", "reason": str(exc)}], indent=2)
                + "\n",
                encoding="utf-8",
            )
            (stage / "cost-sensitivity.csv").write_text(
                "status\nrejected_input\n", encoding="utf-8"
            )
            stage.replace(output_dir)
            return {"status": "rejected_input", "scenario_count": 0}

        from dataclasses import replace

        rows = []
        scenario_root = stage / "scenarios"
        scenario_root.mkdir()
        clock = None
        for scenario in build_cost_scenarios():
            request = replace(
                base_request,
                config=replace(
                    base_request.config,
                    commission_bps=scenario.commission_bps,
                    slippage_bps=scenario.slippage_bps,
                    fx_cost_bps=scenario.fx_cost_bps,
                ),
            )
            result = run_usd_price_replay(request)
            clock = _clock(request, result)
            write_usd_price_replay_bundle(
                scenario_root / scenario.scenario_id,
                result=result,
                run_id=scenario.scenario_id,
                research_clock=clock,
                producer={
                    "repository": "runchengxie/2026-quant-competition",
                    "version": "0.1.0",
                    "commit": "unknown",
                    "backend": "usd.price_ledger",
                    "backend_version": "1",
                },
                configuration_sha256=lock["configuration_sha256"],
                input_refs=_input_refs(inputs),
            )
            rows.append(_metrics(scenario, result))
        pd.DataFrame(rows).to_csv(stage / "cost-sensitivity.csv", index=False)
        (stage / "result-note.md").write_text(
            "# Global ETF next-open replay\n\n"
            "This is a research diagnostic, not executable and not a performance claim. "
            "No broker orders were submitted. The first regular-hours trade open is a modeled "
            "reference; daily close availability and same-session FX midpoint timing are assumed. "
            "Results use USD price NAV, exclude dividends, and do not represent total returns.\n",
            encoding="utf-8",
        )
        stage.replace(output_dir)
        return {
            "status": "completed",
            "scenario_count": len(rows),
            "output_dir": str(output_dir),
        }
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--json", action="store_true", help="Emit JSON (default)")
    args = parser.parse_args(argv)
    try:
        result = run_experiment(args.config, args.output_dir)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError):
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "issue_codes": ["INVALID_EXPERIMENT"],
                    "orders_submitted": False,
                    "accepted_research": False,
                }
            )
        )
        return 2
    print(json.dumps(result))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
