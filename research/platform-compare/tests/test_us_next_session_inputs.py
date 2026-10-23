"""Execution evidence remains distinct from a daily signal dataset."""

import hashlib
import json
from pathlib import Path

import pytest


def fixture_spec(tmp_path):
    import pandas as pd
    from platform_compare.next_open.calendar import CALENDAR_PACKAGE_VERSION

    bars = tmp_path / "AAPL.csv"
    pd.DataFrame(
        {
            "date": ["2025-03-07", "2025-03-10", "2025-03-11"],
            "open": [100, 101, 102],
            "close": [100, 102, 103],
        }
    ).to_csv(bars, index=False)
    actions = tmp_path / "actions.json"
    actions.write_text(
        json.dumps(
            dict(
                schema="competition.us_action_coverage.v1",
                synthetic=True,
                start="2025-03-07",
                end="2025-03-11",
                products=["AAPL"],
                events=[],
                source="synthetic_contract_vector",
                review_id=None,
            )
        )
    )
    spec = dict(
        schema="competition.us_next_session_inputs.v1",
        synthetic=True,
        calendar=dict(
            name="XNYS", package="exchange_calendars", version=CALENDAR_PACKAGE_VERSION
        ),
        signal_basis="raw",
        execution_basis="raw",
        quote_currency="USD",
        sizing_mode="fractional",
        instruments={"AAPL": dict(currency="USD", lot_size=1)},
        files={
            "AAPL": dict(
                path=str(bars), sha256=hashlib.sha256(bars.read_bytes()).hexdigest()
            )
        },
        actions=dict(
            path=str(actions), sha256=hashlib.sha256(actions.read_bytes()).hexdigest()
        ),
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
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    return path, spec


def write_spec(path, spec):
    path.write_text(json.dumps(spec))


def test_loader_binds_files_and_separate_price_basis(tmp_path):
    from platform_compare.us_next_session.inputs import load_us_inputs

    path, spec = fixture_spec(tmp_path)
    loaded = load_us_inputs(path)
    assert set(loaded.assets) == {"AAPL"}
    Path(spec["files"]["AAPL"]["path"]).write_text("revised")
    with pytest.raises(ValueError, match="HASH"):
        load_us_inputs(path)


@pytest.mark.parametrize(
    "mutation", ["basis", "actions", "nonempty", "integral_lot", "false_real"]
)
def test_unsupported_or_unverified_evidence_blocks(tmp_path, mutation):
    from platform_compare.us_next_session.inputs import load_us_inputs

    path, spec = fixture_spec(tmp_path)
    if mutation == "basis":
        spec["signal_basis"] = "split_adjusted"
    elif mutation == "actions":
        spec["actions"] = None
    elif mutation == "integral_lot":
        spec["sizing_mode"] = "integral"
        spec["instruments"]["AAPL"]["lot_size"] = None
    elif mutation == "false_real":
        spec["synthetic"] = False
    else:
        actions_path = Path(spec["actions"]["path"])
        actions = json.loads(actions_path.read_text())
        actions["events"] = [dict(date="2025-03-10", product="AAPL", kind="dividend")]
        actions_path.write_text(json.dumps(actions))
        spec["actions"]["sha256"] = hashlib.sha256(
            actions_path.read_bytes()
        ).hexdigest()
    write_spec(path, spec)
    with pytest.raises(ValueError):
        load_us_inputs(path)
