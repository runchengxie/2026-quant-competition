"""Exercise installed offline controls, continuous accounts and execution contracts."""

import argparse
import json
from pathlib import Path

from .check_controls_delivery import check_controls_delivery
from .check_observation_delivery import check_observation_delivery
from .datasets.daily_storage import safe_path
from .datasets.storage import digest, write_json
from .team.config import load_config
from .team.execution_readiness import audit_execution_inputs
from .team.run import run_experiment


def execution_fixture(output: Path):
    """Independent literal vector bound to the leaf's locked calendar contract."""
    output.mkdir(parents=True, exist_ok=True)
    bars = output / "AAPL.csv"
    bars.write_text(
        "date,open,close\n2025-03-07,100,100\n2025-03-10,101,102\n2025-03-11,102,103\n",
        encoding="utf-8",
    )
    actions = output / "actions.json"
    write_json(
        actions,
        dict(
            schema="competition.us_action_coverage.v1",
            synthetic=True,
            start="2025-03-07",
            end="2025-03-11",
            products=["AAPL"],
            events=[],
            source="synthetic_contract_vector",
            review_id=None,
        ),
    )
    spec = dict(
        schema="competition.us_next_session_inputs.v1",
        synthetic=True,
        calendar=dict(name="XNYS", package="exchange_calendars", version="4.13.2"),
        signal_basis="raw",
        execution_basis="raw",
        quote_currency="USD",
        sizing_mode="fractional",
        instruments={"AAPL": dict(currency="USD", lot_size=1)},
        files={"AAPL": dict(path=str(bars), sha256=digest(bars))},
        actions=dict(path=str(actions), sha256=digest(actions)),
        schedule=[
            dict(
                decision_id="first",
                signal_at="2025-03-07T21:00:00Z",
                available_at="2025-03-07T21:01:00Z",
                decision_at="2025-03-07T21:02:00Z",
                weights={"AAPL": 1},
            )
        ],
    )
    path = output / "spec.json"
    write_json(path, spec)
    return path, spec


def check_strategy_evidence_delivery(config, output_root: Path):
    output = safe_path(output_root)
    output.mkdir(parents=True, exist_ok=False)
    controls = check_controls_delivery(config, output / "controls")
    observations = check_observation_delivery(config, output / "observations")
    path, _ = execution_fixture(output / "execution-inputs")
    dispatched = run_experiment("us-next-session", config, path, output / "execution")
    if dispatched["issue_codes"]:
        raise ValueError("SYNTHETIC_EXECUTION_DELIVERY_FAILED")
    execution = json.loads((output / "execution/run.json").read_text())
    if execution["status"] != "completed" or execution["orders_submitted"] != 0:
        raise ValueError("SYNTHETIC_EXECUTION_CONTRACT_FAILED")
    manifest = output / "cached-daily.json"
    write_json(
        manifest,
        dict(
            schema="competition.dataset_manifest.v2",
            synthetic=True,
            spec=dict(market="US", quote_currency="USD", price_basis="raw"),
        ),
    )
    readiness = audit_execution_inputs(
        dict(
            schema="competition.us_execution_readiness_spec.v1",
            manifests=[dict(path=str(manifest), sha256=digest(manifest))],
        )
    )
    if readiness["status"] != "blocked" or "metrics" in readiness:
        raise ValueError("DAILY_CACHE_MUST_NOT_AUTHORIZE_EXECUTION")
    write_json(output / "readiness.json", readiness)
    report = dict(
        schema="competition.strategy_evidence_delivery.v1",
        synthetic=True,
        controls_completed=controls["completed"],
        observation_receipts=observations["receipts"],
        continuous_accounts=observations["continuous_accounts"],
        execution_status=execution["status"],
        cached_execution_status=readiness["status"],
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
            check_strategy_evidence_delivery(
                load_config(args.config), args.output_root
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
