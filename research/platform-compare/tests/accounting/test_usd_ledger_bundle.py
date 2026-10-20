# Derived from quant-platform 28a32ba707ad72d1eb68cde5075663e1b3819ac7.
# Modified for the competition namespace/identity; licensed under Apache-2.0.
# See accounting/ORIGIN.json and LICENSE-APACHE-2.0.txt for provenance and terms.
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import localcontext
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
from platform_compare.accounting.contracts import ResearchClock
from usd_ledger_fixtures import REF, D, at, decision, instrument, price, request

from platform_compare.accounting.backtest_bundle import BacktestEvidenceTier
from platform_compare.accounting.backtest_bundle_io import read_backtest_bundle
from platform_compare.accounting.usd_ledger import run_usd_price_replay
from platform_compare.accounting.usd_ledger_bundle import _validate_daily, write_usd_price_replay_bundle
from platform_compare.accounting.usd_ledger_models import (
    USDFXObservation,
    USDModeledExecutionPrice,
    USDValidationError,
)


def test_daily_nav_attribution_validation_scales_tolerance_to_book_value():
    previous = D("101900.54705038579563541177906091430535365285575171")
    nav = D("101899.25559573451200155872588590763995443766930168")
    fx_pnl = D("-1.2914546512836338530531750066653992151864500212752")
    daily = pd.DataFrame(
        [
            {
                "valuation_at": datetime(2026, 1, 1, tzinfo=UTC),
                "cash_usd": D(0),
                "positions_usd": nav,
                "nav_usd": nav,
                "local_price_pnl_usd": D(0),
                "fx_pnl_usd": fx_pnl,
                "costs_usd": D(0),
                "nav_return": D(0),
            }
        ]
    )
    result = SimpleNamespace(diagnostics={"initial_cash_usd": previous}, daily=daily)

    with localcontext() as context:
        context.prec = 50
        daily.at[0, "nav_return"] = nav / previous - 1
        _validate_daily(result)


def result():
    return run_usd_price_replay(
        request(
            prices=(price(), price(hour=1), price(day=2), price(day=2, hour=1)),
            decisions=(decision(), decision(day=2, weights={})),
        )
    )


def modeled_result(
    *, valuation_times=None, decisions=None, cfg_overrides=None, modeled_prices=None, prices=None
):
    from usd_ledger_fixtures import config

    return run_usd_price_replay(
        request(
            instruments=(instrument(currency="GBP"),),
            prices=prices or (price(), price(hour=1), price(day=2), price(day=2, hour=1)),
            decisions=decisions or (decision(),),
            valuation_times=valuation_times or (at(1), at(2), at(3)),
            fx=(
                USDFXObservation(
                    "GBP",
                    "USD",
                    at(1),
                    at(1),
                    D("1.25"),
                    "quote_per_base",
                    REF,
                    "assumed_market_session",
                ),
            ),
            modeled_execution_prices=modeled_prices
            or (
                USDModeledExecutionPrice(
                    "A",
                    date(2026, 1, 1),
                    at(1, 1),
                    D("10"),
                    "currency_per_share",
                    REF,
                    "synthetic-session.v1",
                    "synthetic-open.v1",
                ),
            ),
            config=config(
                **(
                    {
                        "fx_pairs": {"GBP": ("GBP", "USD")},
                        "commission_bps": D("5"),
                        "slippage_bps": D("5"),
                        "fx_cost_bps": D("5"),
                        "allow_assumed_availability": True,
                        "allow_modeled_execution_prices": True,
                    }
                    | (cfg_overrides or {})
                )
            ),
        )
    )


def root_clock():
    return ResearchClock(
        "UTC",
        at(1),
        at(1),
        at(1),
        at(3),
        "synthetic-run.v1",
        "synthetic.v1",
        at(1, 1),
        at(1, 1),
        at(2, 1),
    )


def publish(path, replay=None, **overrides):
    fields: dict[str, Any] = {
        "result": replay or result(),
        "run_id": "synthetic-usd",
        "research_clock": root_clock(),
        "producer": {
            "repository": "quant-platform",
            "version": "0.0.1",
            "commit": "synthetic",
            "backend": "usd.price_ledger",
        },
        "configuration_sha256": "c" * 64,
        "input_refs": [REF.to_mapping()],
    }
    return write_usd_price_replay_bundle(path, **(fields | overrides))


def test_two_decision_bundle_roundtrips_hashes_and_decimal_records(tmp_path):
    path = tmp_path / "bundle"
    manifest = publish(path)
    assert read_backtest_bundle(path) == manifest
    assert manifest.evidence_tier is BacktestEvidenceTier.DIAGNOSTIC
    assert manifest.backend_capabilities["order_lifecycle"] is False
    assert pd.read_parquet(path / "orders.parquet").empty
    assert pd.read_parquet(path / "fills.parquet").empty
    diagnostics = json.loads((path / "diagnostics.json").read_text(encoding="utf-8"))
    assert len(diagnostics["decision_clocks"]) == 2
    assert isinstance(diagnostics["daily"][1]["nav_usd"], str)
    assert D(diagnostics["daily"][1]["nav_usd"]) == D("100")
    assert D(diagnostics["transactions"][0]["executed_delta"]) == D("5")
    assert diagnostics["summary"]["return_basis"] == "usd_price_nav"
    assert diagnostics["usd_reconciliation"]["status"] == "passed"
    with pytest.raises(FileExistsError):
        publish(path)
    (path / "diagnostics.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        read_backtest_bundle(path)


@pytest.mark.parametrize(
    "changes",
    [
        {"input_refs": []},
        {"configuration_sha256": "bad"},
        {"input_refs": [{"artifact_id": "other", "sha256": "a" * 64}]},
        {"research_clock": replace(root_clock(), valuation_at=at(4))},
        {"research_clock": replace(root_clock(), decision_at=at(1, 1))},
    ],
)
def test_invalid_lineage_hashes_or_root_clock_cannot_publish(tmp_path, changes):
    with pytest.raises(ValueError):
        publish(tmp_path / "bundle", **changes)
    assert not (tmp_path / "bundle").exists()


@pytest.mark.parametrize(
    "table,column,value",
    [
        ("daily", "cash_usd", D("101")),
        ("daily", "nav_usd", D("999")),
        ("daily", "local_price_pnl_usd", D("1")),
        ("daily", "costs_usd", D("1")),
        ("daily", "nav_return", D("0.1")),
        ("holdings", "quantity", D("8")),
        ("holdings", "value_usd", D("51")),
        ("holdings", "weight", D("0.8")),
        ("transactions", "executed_delta", D("9")),
        ("transactions", "costs_usd", D("1")),
        ("transactions", "cash_after_usd", D("80")),
        ("transactions", "notional_usd", D("20")),
    ],
)
def test_mutated_accounting_cannot_publish_successful_bundle(tmp_path, table, column, value):
    r = result()
    frame = getattr(r, table).copy(deep=True)
    frame.loc[0, column] = value
    with pytest.raises(USDValidationError):
        publish(tmp_path / "bundle", replace(r, **{table: frame}))
    assert not (tmp_path / "bundle").exists()


@pytest.mark.parametrize(
    "field,changes",
    [
        ("summary", {"evidence_tier": "execution_aware"}),
        ("summary", {"return_basis": "total_return"}),
        ("summary", {"orders_submitted": True}),
        ("diagnostics", {"backend_capabilities": {"order_lifecycle": True}}),
    ],
)
def test_capability_escalation_cannot_publish(tmp_path, field, changes):
    r = result()
    with pytest.raises(USDValidationError):
        publish(tmp_path / "bundle", replace(r, **{field: dict(getattr(r, field)) | changes}))


def test_all_cash_bundle_retains_dates_and_has_no_fabricated_lifecycle(tmp_path):
    r = run_usd_price_replay(request(instruments=(), prices=(), decisions=()))
    m = publish(
        tmp_path / "cash", r, input_refs=[{"artifact_id": "synthetic-config", "sha256": "c" * 64}]
    )
    assert m.evidence_tier is BacktestEvidenceTier.DIAGNOSTIC
    assert len(pd.read_parquet(tmp_path / "cash" / "daily_nav.parquet")) == 3


def test_mutated_performance_summary_cannot_publish(tmp_path):
    r = result()
    with pytest.raises(USDValidationError):
        publish(
            tmp_path / "bundle", replace(r, summary=dict(r.summary) | {"cumulative_return": D("9")})
        )


def test_duplicate_decision_clock_cannot_publish(tmp_path):
    r = result()
    with pytest.raises(USDValidationError):
        publish(tmp_path / "bundle", replace(r, decision_clocks=(r.decision_clocks[0],) * 2))


def test_negative_target_weight_cannot_publish(tmp_path):
    r = result()
    targets = r.targets.copy(deep=True)
    targets.loc[0, "target_weight"] = D("-0.5")
    with pytest.raises(USDValidationError):
        publish(tmp_path / "bundle", replace(r, targets=targets))


def test_offsetting_price_and_fx_pnl_mutations_cannot_publish(tmp_path):
    r = result()
    daily = r.daily.copy(deep=True)
    daily.loc[1, "local_price_pnl_usd"] = D("10")
    daily.loc[1, "fx_pnl_usd"] = D("-10")
    with pytest.raises(USDValidationError):
        publish(tmp_path / "bundle", replace(r, daily=daily))


def test_target_weight_must_match_frozen_decision_sizing(tmp_path):
    r = result()
    targets = r.targets.copy(deep=True)
    targets.loc[0, "target_weight"] = D("0.9")
    with pytest.raises(USDValidationError):
        publish(tmp_path / "bundle", replace(r, targets=targets))


def test_target_mark_source_must_belong_to_lineage(tmp_path):
    r = result()
    targets = r.targets.copy(deep=True)
    targets.at[0, "price_source_ref"] = {
        "artifact_id": "unlisted-decision-source",
        "sha256": "b" * 64,
    }
    with pytest.raises(USDValidationError):
        publish(tmp_path / "bundle", replace(r, targets=targets))


def test_bundle_round_trip_preserves_modeled_reference_and_assumptions(tmp_path):
    path = tmp_path / "modeled"
    replay = modeled_result()
    manifest = publish(path, replay)
    diagnostics = json.loads((path / "diagnostics.json").read_text(encoding="utf-8"))
    transaction = diagnostics["transactions"][0]
    assert read_backtest_bundle(path) == manifest
    assert transaction["execution_evidence_kind"] == "modeled_reference"
    assert transaction["modeled_price_session_date"] == "2026-01-01"
    assert transaction["modeled_price_model_id"] == "synthetic-open.v1"
    assert transaction["execution_eligible"] is False
    assert transaction["fx_availability_basis"] == "assumed_market_session"
    assert D(transaction["slippage_usd"]) == D("0.025")
    assert D(transaction["execution_price"]) == D("10.005")
    assert D(transaction["commission_usd"]) == D("0.025")
    assert D(transaction["fx_cost_usd"]) == D("0.025")
    assert transaction["price_source_ref"] == REF.to_mapping()
    assert diagnostics["summary"]["orders_submitted"] is False
    assert diagnostics["summary"]["evidence_tier"] == "diagnostic"


@pytest.mark.parametrize(
    "column,value",
    [
        ("modeled_price_model_id", "different-valid-model.v1"),
        ("modeled_price_session_date", date(2026, 1, 2)),
    ],
)
def test_bundle_rejects_changed_modeled_execution_provenance(tmp_path, column, value):
    replay = modeled_result()
    transactions = replay.transactions.copy(deep=True)
    transactions.at[0, column] = value
    with pytest.raises(USDValidationError):
        publish(tmp_path / "bad", replace(replay, transactions=transactions))


def test_modeled_mark_at_open_keeps_metadata_for_valuation_and_publication(tmp_path):
    replay = modeled_result(valuation_times=(at(1), at(1, 1), at(2), at(3)))
    manifest = publish(tmp_path / "at-open", replay)
    assert manifest.evidence_tier is BacktestEvidenceTier.DIAGNOSTIC
    open_mark = replay.holdings.loc[replay.holdings.valuation_at == at(1, 1)].iloc[0]
    assert open_mark.execution_evidence_kind == "modeled_reference"
    diagnostics = json.loads(
        (tmp_path / "at-open" / "diagnostics.json").read_text(encoding="utf-8")
    )
    assert diagnostics["holdings"][0]["execution_evidence_kind"] == "modeled_reference"


def test_zero_quantity_integral_sell_keeps_requested_direction_for_publication(tmp_path):
    replay = modeled_result(
        decisions=(decision(), decision(day=2, weights={"A": D("0.45")})),
        cfg_overrides={"sizing_mode": "integral", "slippage_bps": D("100")},
        modeled_prices=(
            USDModeledExecutionPrice(
                "A",
                date(2026, 1, 1),
                at(1, 1),
                D("10"),
                "currency_per_share",
                REF,
                "synthetic-session.v1",
                "synthetic-open.v1",
            ),
            USDModeledExecutionPrice(
                "A",
                date(2026, 1, 2),
                at(2, 1),
                D("10"),
                "currency_per_share",
                REF,
                "synthetic-session.v1",
                "synthetic-open.v1",
            ),
        ),
        prices=(price(), price(hour=1), price(day=2), price(day=2, hour=1), price(day=3)),
    )
    zero_sell = replay.transactions.iloc[-1]
    assert zero_sell.requested_delta < 0 and zero_sell.executed_delta == 0
    manifest = publish(tmp_path / "zero-sell", replay)
    assert manifest.evidence_tier is BacktestEvidenceTier.DIAGNOSTIC


@pytest.mark.parametrize(
    "column,value",
    [
        ("price_source_ref", {"artifact_id": "synthetic-prices", "sha256": "b" * 64}),
        ("modeled_price_model_id", None),
        ("execution_eligible", True),
    ],
)
def test_bundle_rejects_corrupted_modeled_reference_lineage_or_eligibility(tmp_path, column, value):
    replay = modeled_result()
    transactions = replay.transactions.copy(deep=True)
    transactions.at[0, column] = value
    with pytest.raises(USDValidationError):
        publish(tmp_path / "bad", replace(replay, transactions=transactions))


def test_verified_bundle_validation_remains_unchanged(tmp_path):
    manifest = publish(tmp_path / "verified", result())
    assert manifest.evidence_tier is BacktestEvidenceTier.DIAGNOSTIC
