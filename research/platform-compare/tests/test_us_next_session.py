"""Session timing and cash funding use the existing independent USD ledger."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from test_us_next_session_inputs import fixture_spec, write_spec


def request(tmp_path, fee=Decimal(20), mutate=None):
    from platform_compare.us_next_session.inputs import load_us_inputs
    from platform_compare.us_next_session.adapter import build_us_replay_request

    path, spec = fixture_spec(tmp_path)
    if mutate:
        mutate(spec)
        write_spec(path, spec)
    return build_us_replay_request(load_us_inputs(path), fee_bps=fee)


def test_friday_to_monday_dst_and_fee_funding(tmp_path):
    from platform_compare.accounting.usd_ledger import run_usd_price_replay

    value = request(tmp_path)
    assert value.decisions[0].execution_times["AAPL"] == datetime(
        2025, 3, 10, 13, 30, tzinfo=timezone.utc
    )
    assert value.config.initial_cash == Decimal(100000)
    assert value.config.return_basis == "price"
    assert value.config.allow_modeled_execution_prices
    result = run_usd_price_replay(value)
    assert all(c >= 0 for c in result.daily["cash_usd"])
    assert sum(result.daily["costs_usd"]) > 0


@pytest.mark.parametrize(
    "field,value",
    [("available_at", "2025-03-07T21:01:00"), ("decision_at", "2025-03-07T20:59:00Z")],
)
def test_unaware_or_noncausal_clock_is_rejected(tmp_path, field, value):
    with pytest.raises(ValueError):
        request(tmp_path, mutate=lambda s: s["schedule"][0].update({field: value}))


def test_missing_first_session_cannot_skip_to_later_bar(tmp_path):
    from platform_compare.us_next_session.inputs import load_us_inputs
    from platform_compare.us_next_session.adapter import build_us_replay_request

    path, _ = fixture_spec(tmp_path)
    inputs = load_us_inputs(path)
    inputs.assets["AAPL"].drop(index=1, inplace=True)
    with pytest.raises(ValueError, match="missing source session"):
        build_us_replay_request(inputs, fee_bps=Decimal(20))


def test_integral_sizing_preserves_residual_cash(tmp_path):
    from platform_compare.accounting.usd_ledger import run_usd_price_replay

    value = request(tmp_path, mutate=lambda s: s.update(sizing_mode="integral"))
    result = run_usd_price_replay(value)
    assert result.daily.iloc[-1]["cash_usd"] > 0
    assert all(q == int(q) for q in result.holdings["quantity"])


def test_availability_after_monday_open_requires_tuesday(tmp_path):
    value = request(
        tmp_path,
        mutate=lambda s: s["schedule"][0].update(
            available_at="2025-03-10T13:31:00Z", decision_at="2025-03-10T13:32:00Z"
        ),
    )
    assert value.decisions[0].execution_times["AAPL"] == datetime(
        2025, 3, 11, 13, 30, tzinfo=timezone.utc
    )


def test_holiday_and_early_close_do_not_create_a_friday_trade(tmp_path):
    import hashlib
    import json
    from pathlib import Path

    import pandas as pd
    from platform_compare.us_next_session.inputs import load_us_inputs
    from platform_compare.us_next_session.adapter import build_us_replay_request

    path, spec = fixture_spec(tmp_path)
    prices = Path(spec["files"]["AAPL"]["path"])
    frame = pd.read_csv(prices)
    frame["date"] = ["2025-07-03", "2025-07-07", "2025-07-08"]
    frame.to_csv(prices, index=False)
    spec["files"]["AAPL"]["sha256"] = hashlib.sha256(prices.read_bytes()).hexdigest()
    actions = Path(spec["actions"]["path"])
    evidence = json.loads(actions.read_text())
    evidence.update(start="2025-07-03", end="2025-07-08")
    actions.write_text(json.dumps(evidence))
    spec["actions"]["sha256"] = hashlib.sha256(actions.read_bytes()).hexdigest()
    spec["schedule"][0].update(
        signal_at="2025-07-03T17:00:00Z",
        available_at="2025-07-03T17:01:00Z",
        decision_at="2025-07-03T17:02:00Z",
    )
    write_spec(path, spec)
    value = build_us_replay_request(load_us_inputs(path), fee_bps=Decimal(20))
    assert value.decisions[0].execution_times["AAPL"] == datetime(
        2025, 7, 7, 13, 30, tzinfo=timezone.utc
    )


def test_installed_cli_writes_diagnostic_bundle(tmp_path):
    import json
    import subprocess
    import sys

    path, _ = fixture_spec(tmp_path)
    output = tmp_path / "delivery"
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "platform_compare.us_next_session.run",
            "--config",
            str(path),
            "--output-root",
            str(output),
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert child.returncode == 0, child.stderr
    value = json.loads(child.stdout)
    assert value["return_basis"] == "usd_price_nav"
    assert value["orders_submitted"] == 0
    assert value["model_id"] == "us-next-session-price-nav.v1"
    assert value["synthetic"] is True
    assert (output / "bundle").is_dir()


@pytest.mark.parametrize(
    "fees",
    [
        (Decimal(20), Decimal(40)),
        (
            Decimal("20.00000000000000000000000000001"),
            Decimal("20.00000000000000000000000000002"),
        ),
    ],
)
def test_fee_scenarios_have_distinct_configuration_identities(tmp_path, fees):
    import json
    from platform_compare.us_next_session.run import run

    path, _ = fixture_spec(tmp_path)
    hashes = []
    for fee in fees:
        target = tmp_path / f"fee-{fee}"
        run(path, target, fee_bps=fee)
        manifest = json.loads((target / "bundle/manifest.json").read_text())
        hashes.append(manifest["artifact_envelope"]["configuration_sha256"])
    assert hashes[0] != hashes[1]
