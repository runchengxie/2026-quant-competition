"""Root tooling exchanges artifacts with the optional provider process only."""

from copy import deepcopy
from datetime import date, timedelta
import json
import subprocess
import sys

import pytest

from competition_tools.accounting_comparison import (
    bind_clocks,
    compare_verified,
    digest,
    monthly_export,
)
from strategies.hk_low_frequency.backtest import (
    DailyBar,
    HKBacktestConfig,
    run_monthly_backtest,
)


def legacy():
    cfg = {
        "commission_bps": 0.0,
        "slippage_bps": 0.0,
        "lookbacks": [2],
        "momentum_weights": [1.0],
        "volatility_window": 2,
        "top_k": 1,
        "max_weight": 0.6,
        "cash_weight": 0.0,
        "mode": "pure_momentum",
    }
    return dict(
        schema_version="competition.legacy_decisions.v1",
        producer="root-monthly",
        strategy_id="pure_momentum",
        market="US",
        frequency="monthly",
        synthetic=True,
        input_fingerprint="a" * 64,
        legacy_config=cfg,
        legacy_config_fingerprint=digest(cfg),
        decisions=[
            dict(
                source_date="2026-01-31",
                execution_date="2026-02-01",
                weights={"US.DEMO_A": ".6"},
            )
        ],
        legacy=dict(
            initial_cash="100",
            final_nav="110",
            observations=2,
            commission_bps="0",
            slippage_bps="0",
            turnover_basis="sum_absolute_target_weight_changes",
            return_basis="monthly_constant_weight_price_proxy",
            cash_model="residual_weight_without_fx",
        ),
    )


def clocks(value=None):
    value = legacy() if value is None else value
    clock = dict(
        schema_version="research.clock.v1",
        timezone="UTC",
        information_cutoff_at="2026-01-31T16:00:00Z",
        signal_at="2026-01-31T16:00:00Z",
        decision_at="2026-01-31T16:01:00Z",
        valuation_at="2026-02-02T16:00:00Z",
        timing_policy_id="synthetic-explicit.v1",
        trading_calendar_ref="synthetic.v1",
        earliest_order_at="2026-02-01T09:00:00Z",
        execution_window_start_at="2026-02-01T09:00:00Z",
        execution_window_end_at="2026-02-01T09:00:00Z",
    )
    return dict(
        schema_version="competition.decision_clocks.v1",
        input_fingerprint=value["input_fingerprint"],
        legacy_config_fingerprint=value["legacy_config_fingerprint"],
        decisions={
            "2026-02-01": dict(
                source_date="2026-01-31",
                clock=clock,
                execution_times={"US.DEMO_A": "2026-02-01T09:00:00Z"},
            )
        },
    )


def projection(value, clock_map):
    return dict(
        schema_version="competition.accounting_result.v1",
        status="diagnostic",
        provider=dict(
            repository="quant-platform",
            commit="28a32ba707ad72d1eb68cde5075663e1b3819ac7",
        ),
        market=value["market"],
        synthetic=value["synthetic"],
        input_fingerprint="b" * 64,
        upstream_input_fingerprint=value["input_fingerprint"],
        config_fingerprint="c" * 64,
        schedule_fingerprint=digest(bind_clocks(value, clock_map)),
        manifest_fingerprint="d" * 64,
        initial_cash_usd="100",
        final_nav_usd="112",
        final_cash_usd="40",
        final_positions_usd="72",
        total_costs_usd="0",
        traded_notional_usd="60",
        sizing_mode="fractional",
        cost_assumptions=dict(commission_bps="0", slippage_bps="0", fx_cost_bps="0"),
        return_basis="usd_price_nav",
        orders_submitted=False,
        observations=2,
        transactions=1,
        order_lifecycle=False,
    )


def test_same_schedule_and_model_differences_are_explicit():
    value = legacy()
    cm = clocks()
    owner = projection(value, cm)
    result = compare_verified(value, cm, owner)
    assert result["status"] == "diagnostic"
    assert result["nav_difference_usd"] == "2"
    assert result["models"]["legacy"] == "monthly_constant_weight_price_proxy"
    assert result["owner"]["final_cash_usd"] == "40"
    assert result["owner"]["sizing_mode"] == "fractional"
    assert result["accepted_research"] is False
    assert "quantity_drift" in result["model_differences"]
    assert str(
        clocks()["decisions"]["2026-02-01"]["clock"]["decision_at"]
    ) in json.dumps(bind_clocks(value, cm))


@pytest.mark.parametrize(
    "change",
    [
        "missing_clock",
        "future_cutoff",
        "wrong_source_date",
        "extra_clock",
        "changed_config",
        "changed_input",
        "wrong_schedule",
        "wrong_cost",
        "unknown_owner_field",
    ],
)
def test_contradictory_or_date_only_evidence_blocks(change):
    value = legacy()
    cm = clocks()
    owner = projection(value, cm)
    if change == "missing_clock":
        cm = None
    elif change == "future_cutoff":
        cm["decisions"]["2026-02-01"]["clock"]["information_cutoff_at"] = (
            "2026-02-01T16:00:00Z"
        )
    elif change == "wrong_source_date":
        cm["decisions"]["2026-02-01"]["source_date"] = "2026-02-01"
    elif change == "extra_clock":
        cm["decisions"]["2026-02-02"] = deepcopy(cm["decisions"]["2026-02-01"])
    elif change == "changed_config":
        value["legacy_config"]["commission_bps"] = 5.0
    elif change == "changed_input":
        owner["upstream_input_fingerprint"] = "f" * 64
    elif change == "wrong_schedule":
        owner["schedule_fingerprint"] = "f" * 64
    elif change == "wrong_cost":
        owner["cost_assumptions"]["commission_bps"] = "5"
    elif change == "unknown_owner_field":
        owner["private_account"] = "PRIVATE_SENTINEL"
    with pytest.raises(ValueError):
        compare_verified(value, cm, owner)


def test_monthly_export_uses_actual_selection_without_changing_legacy():
    def bars(scale):
        return [
            DailyBar(
                (date(2026, 1, 1) + timedelta(days=i)).isoformat(),
                100 + scale * i,
                1000,
            )
            for i in range(70)
        ]

    history = {"HK.DEMO_A": bars(1), "HK.DEMO_B": bars(0.1)}
    benchmark = bars(0.5)
    cfg = HKBacktestConfig(
        lookbacks=(2,),
        momentum_weights=(1.0,),
        volatility_window=2,
        top_k=1,
        max_weight=0.6,
    )
    expected = run_monthly_backtest(history, benchmark, cfg)
    out = monthly_export(
        history,
        benchmark,
        cfg,
        market="HK",
        synthetic=True,
        input_fingerprint="a" * 64,
        initial_cash="100",
    )
    assert len(out["decisions"]) == len(expected.rebalances)
    assert all(
        row["weights"] == {"HK.DEMO_A": "0.6", "HK.DEMO_B": "0"}
        for row in out["decisions"]
    )
    assert out["strategy_id"] == "momentum_volatility"
    assert out["frequency"] == "monthly"
    assert out["legacy_config_fingerprint"] == digest(out["legacy_config"])
    assert out["legacy"]["final_nav"] == str(
        100.0 * (1 + expected.metrics.cumulative_return)
    )
    with pytest.raises(ValueError, match="CLOCK_METADATA_REQUIRED"):
        bind_clocks(out, None)


def test_cli_help_and_parser_errors_do_not_expose_private_paths():
    for args, code in [(["--help"], 0), (["--PRIVATE_SENTINEL"], 2)]:
        result = subprocess.run(
            [sys.executable, "-m", "competition_tools.accounting_comparison", *args],
            capture_output=True,
            text=True,
        )
        assert result.returncode == code
        assert "PRIVATE_SENTINEL" not in result.stdout + result.stderr


def test_monthly_export_makes_implicit_zero_targets_explicit():
    def bars(scale):
        return [
            DailyBar(
                (date(2026, 1, 1) + timedelta(days=i)).isoformat(),
                100 + scale * i,
                1000,
            )
            for i in range(40)
        ]

    out = monthly_export(
        {"HK.DEMO_A": bars(1), "HK.DEMO_B": bars(0.1)},
        bars(0.5),
        HKBacktestConfig(
            lookbacks=(2,),
            momentum_weights=(1.0,),
            volatility_window=2,
            top_k=1,
            max_weight=0.6,
        ),
        market="HK",
        synthetic=True,
        input_fingerprint="a" * 64,
        initial_cash="100",
    )
    assert out["decisions"][0]["weights"]["HK.DEMO_B"] == "0"


def test_float_residue_is_bounded_and_reported_without_changing_raw_weights():
    from decimal import Decimal

    value = legacy()
    weights = {"US.DEMO_" + str(i): str(1 / 11) for i in range(11)}
    value["decisions"][0]["weights"] = weights
    cm = clocks(value)
    cm["decisions"]["2026-02-01"]["execution_times"] = {
        code: "2026-02-01T09:00:00Z" for code in weights
    }
    original = deepcopy(value)
    bound = bind_clocks(value, cm)
    assert sum(map(Decimal, bound[0]["weights"].values())) == 1
    assert value == original
    owner = projection(value, cm)
    result = compare_verified(value, cm, owner)
    assert (
        result["weight_mapping_adjustments"][0]["removed_weight"]
        == "0.00000000000000001"
    )
    value["decisions"][0]["weights"]["US.DEMO_0"] = "0.5"
    with pytest.raises(ValueError, match="EXCESS_GROSS_WEIGHT"):
        bind_clocks(value, cm)


@pytest.mark.parametrize("problem", ["request_array", "invalid_commission"])
def test_malformed_root_files_return_only_redacted_json(tmp_path, problem):
    from competition_tools.accounting_comparison import PROVIDER

    value = legacy()
    cm = clocks(value)
    if problem == "invalid_commission":
        value["legacy_config"]["commission_bps"] = "not-a-number"
        value["legacy_config_fingerprint"] = digest(value["legacy_config"])
        cm["legacy_config_fingerprint"] = value["legacy_config_fingerprint"]
    for name, data in [
        ("legacy", value),
        ("clocks", cm),
        ("request", [] if problem == "request_array" else {"provider": PROVIDER}),
    ]:
        (tmp_path / (name + ".json")).write_text(json.dumps(data))
    command = [
        sys.executable,
        "-m",
        "competition_tools.accounting_comparison",
        "--legacy",
        str(tmp_path / "legacy.json"),
        "--clocks",
        str(tmp_path / "clocks.json"),
        "--provider-python",
        sys.executable,
        "--request",
        str(tmp_path / "request.json"),
        "--dataset-root",
        str(tmp_path),
        "--bundle",
        str(tmp_path / "PRIVATE_SENTINEL"),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "blocked"
    assert str(tmp_path) not in result.stdout
    assert "PRIVATE_SENTINEL" not in result.stdout
