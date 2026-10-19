"""The consumer uses an installed fixed owner, never a sibling source import."""

import hashlib
import json
import os
import subprocess
import sys

import pytest

from platform_compare.contracts import digest
from platform_compare.owner_adapter import run_request, verify_bundle

PIN = "28a32ba707ad72d1eb68cde5075663e1b3819ac7"


def clock():
    return {
        "schema_version": "research.clock.v1",
        "timezone": "UTC",
        "information_cutoff_at": "2026-01-01T00:00:00Z",
        "signal_at": "2026-01-01T00:00:00Z",
        "decision_at": "2026-01-01T00:00:00Z",
        "valuation_at": "2026-01-03T00:00:00Z",
        "timing_policy_id": "synthetic-next-mark.v1",
        "trading_calendar_ref": "synthetic.v1",
        "earliest_order_at": "2026-01-01T01:00:00Z",
        "execution_window_start_at": "2026-01-01T01:00:00Z",
        "execution_window_end_at": "2026-01-01T01:00:00Z",
    }


def fixture(tmp_path, *, all_cash=False):
    def price(at, value):
        return {
            "instrument_id": "US.DEMO_A",
            "price_at": at,
            "available_at": at,
            "price": value,
            "unit": "currency_per_share",
            "availability_basis": "verified",
            "session_policy_id": "synthetic-session.v1",
            "execution_eligible": True,
        }

    asset = {
        "schema_version": "competition.accounting_inputs.v1",
        "market": "US",
        "synthetic": True,
        "upstream_input_fingerprint": "a" * 64,
        "instruments": []
        if all_cash
        else [
            {
                "instrument_id": "US.DEMO_A",
                "asset_type": "etf",
                "currency": "USD",
                "lot_size": 1,
                "session_policy_id": "synthetic-session.v1",
            }
        ],
        "prices": []
        if all_cash
        else [
            price("2026-01-01T00:00:00Z", "10"),
            price("2026-01-01T01:00:00Z", "10"),
            price("2026-01-03T00:00:00Z", "20"),
        ],
        "fx": [],
        "decisions": []
        if all_cash
        else [
            {
                "decision_id": "d1",
                "clock": clock(),
                "weights": {"US.DEMO_A": "0.5"},
                "execution_times": {"US.DEMO_A": "2026-01-01T01:00:00Z"},
            }
        ],
        "valuation_times": [
            "2026-01-01T00:00:00Z",
            "2026-01-02T00:00:00Z",
            "2026-01-03T00:00:00Z",
        ],
        "research_clock": clock(),
    }
    config = {
        "initial_cash": "100",
        "sizing_mode": "fractional",
        "commission_bps": "0",
        "slippage_bps": "0",
        "fx_cost_bps": "0",
        "max_price_age_seconds": 432000,
        "max_fx_age_seconds": 432000,
        "fx_pairs": {},
        "allow_assumed_availability": False,
        "return_basis": "price",
        "allow_modeled_execution_prices": False,
    }
    path = tmp_path / "asset.json"
    path.write_text(json.dumps(asset))
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    request = {
        "schema_version": "competition.accounting_request.v1",
        "provider": {"repository": "quant-platform", "commit": PIN},
        "run_id": "synthetic-compare-v1",
        "market": "US",
        "synthetic": True,
        "evidence": "software_diagnostic",
        "input_ref": {
            "artifact_id": "synthetic:prices-v1",
            "relative_path": "asset.json",
            "sha256": sha,
            "size_bytes": path.stat().st_size,
        },
        "input_fingerprint": sha,
        "config": config,
        "config_fingerprint": digest(config),
    }
    req = tmp_path / "request.json"
    req.write_text(json.dumps(request))
    return req, request, asset


def rewrite(tmp_path, request, asset):
    path = tmp_path / "asset.json"
    path.write_text(json.dumps(asset))
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    request["input_ref"].update(sha256=sha, size_bytes=path.stat().st_size)
    request["input_fingerprint"] = sha
    request["config_fingerprint"] = digest(request["config"])
    (tmp_path / "request.json").write_text(json.dumps(request))


@pytest.mark.parametrize("all_cash,expected", [(True, "100"), (False, "150")])
def test_actual_owner_bundle_reconciles_and_hash_reader_rejects_mutation(
    tmp_path, all_cash, expected
):
    req, _, _ = fixture(tmp_path, all_cash=all_cash)
    original = (tmp_path / "asset.json").read_bytes()
    value = run_request(req, tmp_path, tmp_path / "output")
    assert value["status"] == "diagnostic"
    assert value["provider"]["commit"] == PIN
    assert value["final_nav_usd"] == expected
    assert value["orders_submitted"] is False
    verify_bundle(tmp_path / "output")
    assert (tmp_path / "asset.json").read_bytes() == original
    file = next((tmp_path / "output").glob("*.parquet"))
    file.write_bytes(file.read_bytes() + b"\nchanged")
    with pytest.raises(ValueError):
        verify_bundle(tmp_path / "output")


@pytest.mark.parametrize(
    "change",
    [
        {"provider": {"repository": "quant-platform", "commit": "0" * 40}},
        {"config_fingerprint": "0" * 64},
        {"input_fingerprint": "0" * 64},
        {"synthetic": "true"},
        {"extra": "private"},
    ],
)
def test_request_contradictions_rejected(tmp_path, change):
    req, value, _ = fixture(tmp_path)
    req.write_text(json.dumps(value | change))
    with pytest.raises(ValueError):
        run_request(req, tmp_path, tmp_path / "output")


@pytest.mark.parametrize("bad", [True, 10.0, "NaN", "Infinity"])
def test_decimal_money_is_finite_string_not_boolean_or_float(tmp_path, bad):
    req, value, asset = fixture(tmp_path)
    asset["prices"][0]["price"] = bad
    rewrite(tmp_path, value, asset)
    with pytest.raises(ValueError):
        run_request(req, tmp_path, tmp_path / "output")


@pytest.mark.parametrize(
    "change",
    [
        {"unit": "lots"},
        {"available_at": "2026-01-04T00:00:00Z"},
        {"price_at": "2026-01-01T00:00:00.000000001Z"},
    ],
)
def test_units_causality_and_unsupported_precision_fail_closed(tmp_path, change):
    req, value, asset = fixture(tmp_path)
    for price in asset["prices"]:
        price.update(change)
    rewrite(tmp_path, value, asset)
    with pytest.raises(ValueError):
        run_request(req, tmp_path, tmp_path / "output")


def test_changed_bytes_and_escaping_reference_rejected(tmp_path):
    req, value, _ = fixture(tmp_path)
    (tmp_path / "asset.json").write_bytes(b"changed")
    with pytest.raises(ValueError):
        run_request(req, tmp_path, tmp_path / "output")
    value["input_ref"]["relative_path"] = "../asset.json"
    req.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        run_request(req, tmp_path, tmp_path / "output")


def test_configured_costs_and_per_instrument_lot_preserved(tmp_path):
    req, value, asset = fixture(tmp_path)
    value["config"].update(sizing_mode="integral", commission_bps="100")
    asset["instruments"][0]["lot_size"] = 3
    rewrite(tmp_path, value, asset)
    result = run_request(req, tmp_path, tmp_path / "output")
    assert result["final_nav_usd"] == "129.7"
    assert result["total_costs_usd"] == "0.3"


def test_help_parser_errors_and_real_cli_use_installed_provider(tmp_path):
    command = [sys.executable, "-m", "platform_compare.cli"]
    env = dict(os.environ)
    env.pop("DATA_ROOT", None)
    assert (
        subprocess.run(command + ["--help"], env=env, capture_output=True).returncode
        == 0
    )
    req, _, _ = fixture(tmp_path)
    args = [
        "run",
        "--request",
        str(req),
        "--dataset-root",
        str(tmp_path),
        "--output",
        str(tmp_path / "out"),
    ]
    result = subprocess.run(command + args, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert subprocess.run(command + args, env=env, capture_output=True).returncode == 2
    result = subprocess.run(
        command + args + ["D:/private/account/input"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "D:/private" not in result.stdout + result.stderr


@pytest.mark.parametrize("problem", [None, "stale", "future", "unit"])
def test_hk_heterogeneous_lots_and_causal_fx(tmp_path, problem):
    req, value, asset = fixture(tmp_path)
    value["market"] = asset["market"] = "HK"
    value["config"].update(
        initial_cash="1000", sizing_mode="integral", fx_pairs={"HKD": ["HKD", "USD"]}
    )
    original = asset["prices"]
    asset["prices"] = []
    asset["instruments"] = []
    for code, lot, factor in [("HK.DEMO_A", 100, 1), ("HK.DEMO_B", 200, 2)]:
        asset["instruments"].append(
            {
                "instrument_id": code,
                "asset_type": "equity",
                "currency": "HKD",
                "lot_size": lot,
                "session_policy_id": "synthetic-session.v1",
            }
        )
        for row in original:
            asset["prices"].append(
                row | {"instrument_id": code, "price": str(int(row["price"]) * factor)}
            )
    asset["decisions"][0].update(
        weights={"HK.DEMO_A": "0.45", "HK.DEMO_B": "0.45"},
        execution_times={
            "HK.DEMO_A": "2026-01-01T01:00:00Z",
            "HK.DEMO_B": "2026-01-01T01:00:00Z",
        },
    )
    asset["fx"] = [
        {
            "base_currency": "HKD",
            "quote_currency": "USD",
            "price_at": "2026-01-01T00:00:00Z",
            "available_at": "2026-01-01T00:00:00Z",
            "rate": "0.1",
            "unit": "quote_per_base",
            "availability_basis": "verified",
        }
    ]
    if problem == "stale":
        asset["fx"][0].update(
            price_at="2025-12-01T00:00:00Z", available_at="2025-12-01T00:00:00Z"
        )
    if problem == "future":
        asset["fx"][0]["available_at"] = "2026-01-04T00:00:00Z"
    if problem == "unit":
        asset["fx"][0]["unit"] = "ambiguous"
    rewrite(tmp_path, value, asset)
    if problem:
        with pytest.raises(ValueError):
            run_request(req, tmp_path, tmp_path / "out")
    else:
        result = run_request(req, tmp_path, tmp_path / "out")
        assert result["final_nav_usd"] == "1800"
        assert result["total_costs_usd"] == "0"


@pytest.mark.parametrize("bad", [True, 0, -1])
def test_boolean_and_nonpositive_lot_rejected(tmp_path, bad):
    req, value, asset = fixture(tmp_path)
    asset["instruments"][0]["lot_size"] = bad
    rewrite(tmp_path, value, asset)
    with pytest.raises(ValueError):
        run_request(req, tmp_path, tmp_path / "out")


def test_verified_projection_binds_request_and_reads_owner_inventory(tmp_path):
    from platform_compare.owner_adapter import verify_result

    req, value, asset = fixture(tmp_path)
    result = run_request(req, tmp_path, tmp_path / "out")
    assert verify_result(req, tmp_path, tmp_path / "out") == result
    assert not (tmp_path / "out" / "comparison.json").exists()
    value["config"]["commission_bps"] = "1"
    rewrite(tmp_path, value, asset)
    with pytest.raises(ValueError):
        verify_result(req, tmp_path, tmp_path / "out")
