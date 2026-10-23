"""No-network installed manual-import fixture with explicitly synthetic time."""

import argparse
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .check_controls_delivery import reference_return
from .datasets.daily_storage import safe_path
from .datasets.storage import digest, write_json
from .evaluation.controls.catalog import COSTS
from .evaluation.observation_registry import (
    CANDIDATES,
    _history,
    _protocol,
    append_observation,
    freeze_observation,
    utc_time,
)
from .evaluation.study_identity import source_identity
from .team.config import load_config


def synthetic_clock(freeze):
    return utc_time(freeze) + timedelta(days=3)


def check_observation_delivery(config, output_root: Path):
    output = safe_path(output_root)
    output.mkdir(parents=True, exist_ok=False)
    now = datetime.now(timezone.utc)
    first = now.date()
    dates = [(first - timedelta(days=252 - i)).isoformat() for i in range(252)]
    warmups = {}
    for market in CANDIDATES:
        path = output / (market + "-warmup.json")
        write_json(path, dict(dates=dates, close={"SYNTHETIC": [100.0] * 252}))
        warmups[market] = dict(path=str(path), sha256=digest(path))
    template = dict(
        schema="competition.observation_protocol.v1",
        synthetic=True,
        candidates=CANDIDATES,
        costs=COSTS,
        warmup=warmups,
        source_identity=source_identity(Path(__file__).resolve().parents[2]),
        known_cutoff=(
            datetime.combine(first, datetime.min.time(), tzinfo=timezone.utc)
            - timedelta(seconds=1)
        ).isoformat(),
        initial_nav=1,
        valuation="lagged_close_proxy",
        zero_volatility="cash",
        execution_authorized=False,
    )
    registry = output / "registry"
    initial = freeze_observation(template, registry, now=now)
    as_of = synthetic_clock(now)
    for market in CANDIDATES:
        for count in (1, 2):
            scored = [(first + timedelta(days=i)).isoformat() for i in range(count)]
            available = [
                (
                    datetime.combine(
                        first + timedelta(days=i + 1),
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    )
                    + timedelta(minutes=1)
                ).isoformat()
                for i in range(count)
            ]
            value = dict(
                schema="competition.observation_import.v1",
                protocol_id=initial["protocol_id"],
                market=market,
                synthetic=True,
                price_basis="raw" if market == "crypto" else "split_adjusted",
                quote_currency="USDT" if market == "crypto" else "USD",
                availability_basis="synthetic",
                availability_evidence=None,
                available_at=available,
                bars=dict(
                    dates=dates + scored, close={"SYNTHETIC": [100.0] * (252 + count)}
                ),
            )
            path = output / f"{market}-{count}.json"
            write_json(path, value)
            status = append_observation(registry, path, config=config, now=as_of)
            if append_observation(registry, path, config=config, now=as_of) != status:
                raise ValueError("SYNTHETIC_OBSERVATION_NOT_IDEMPOTENT")
    history = _history(registry, _protocol(registry))
    for _, manifest, replay in history:
        for row in replay["results"]:
            expected = reference_return(
                manifest["market"], row["arm_id"], row["fee_bps"]
            )
            if not math.isclose(
                row["output"]["metrics"]["net_return"],
                expected,
                rel_tol=0,
                abs_tol=1e-12,
            ):
                raise ValueError("SYNTHETIC_CONTINUOUS_ACCOUNT_MISMATCH")
    report = dict(
        schema="competition.observation_delivery.v1",
        synthetic=True,
        synthetic_import_clock=as_of.isoformat(),
        freeze_at=now.isoformat(),
        receipts=len(history),
        continuous_accounts=15,
        observations=status["observations"],
        evidence_tier=status["evidence_tier"],
        orders_submitted=0,
    )
    write_json(output / "delivery.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            check_observation_delivery(load_config(args.config), args.output_root),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
