from dataclasses import replace
from datetime import date, timedelta
from decimal import localcontext

import pytest
from test_usd_ledger_inputs import fx
from usd_ledger_fixtures import D, at, config, decision, instrument, price, request

from platform_compare.accounting.usd_ledger import assert_usd_equal, run_usd_price_replay
from platform_compare.accounting.usd_ledger_models import USDModeledExecutionPrice, USDValidationError


def test_interval_nav_tolerance_scales_to_book_value_after_subtraction():
    nav_change = D("-1.29145465128363385305317500666539921518645003")
    attributed = D("-1.2914546512836338530531750066653992151864500212752")
    book_value = D("101900.54705038579563541177906091430535365285575171")

    with localcontext() as context:
        context.prec = 50
        assert_usd_equal(nav_change, attributed, "interval NAV attribution", scale=book_value)
        with pytest.raises(USDValidationError, match="unreconciled interval NAV attribution"):
            assert_usd_equal(
                nav_change,
                attributed + D("1e-30"),
                "interval NAV attribution",
                scale=book_value,
            )


def test_quantities_stay_fixed_and_weights_drift():
    result = run_usd_price_replay(
        request(prices=(price(), price(hour=1), price(day=3, value="20")))
    )
    assert list(result.daily.nav_usd) == [D("100"), D("100"), D("150")]
    assert list(result.daily.cash_usd) == [D("100"), D("50"), D("50")]
    assert list(result.holdings.quantity) == [D("5"), D("5")]
    assert abs(result.holdings.iloc[-1].weight - D(2) / 3) < D("1e-27")
    assert result.summary["cumulative_return"] == D("0.5")
    assert result.summary["orders_submitted"] is False
    assert "sharpe" not in result.summary


@pytest.mark.parametrize("inverse", [False, True])
def test_fx_only_revaluation_is_attributed_without_local_pnl(inverse):
    rows = (
        (fx("USD", "GBP", "0.8"), fx("USD", "GBP", "0.5", day=3))
        if inverse
        else (fx("GBP", "USD", "1.25"), fx("GBP", "USD", "2", day=3))
    )
    pair = ("USD", "GBP") if inverse else ("GBP", "USD")
    r = request(
        instruments=(instrument(currency="GBP"),),
        decisions=(decision(weights={"A": D("0.25")}),),
        fx=rows,
        config=config(fx_pairs={"GBP": pair}),
    )
    result = run_usd_price_replay(r)
    assert result.holdings.iloc[-1].quantity == D("2")
    assert result.daily.iloc[-1].nav_usd == D("115")
    assert result.daily.iloc[-1].fx_pnl_usd == D("15")
    assert result.daily.iloc[-1].local_price_pnl_usd == D("0")


def test_exact_five_dollar_fx_pnl():
    result = run_usd_price_replay(
        request(
            instruments=(instrument(currency="GBP"),),
            decisions=(decision(weights={"A": D("0.25")}),),
            fx=(fx("GBP", "USD", "1.25"), fx("GBP", "USD", "1.5", day=3)),
            config=config(fx_pairs={"GBP": ("GBP", "USD")}),
        )
    )
    assert result.daily.iloc[-1].fx_pnl_usd == D("5")
    assert result.daily.iloc[-1].nav_usd == D("105")


def test_all_cash_preserves_grid_without_requiring_marks():
    r = run_usd_price_replay(request(instruments=(), prices=(), decisions=()))
    assert list(r.daily.nav_usd) == [D("100")] * 3
    assert r.summary["cumulative_return"] == r.summary["max_drawdown"] == r.summary["cagr"] == 0
    assert r.holdings.empty and r.transactions.empty


def test_liquidation_keeps_subsequent_cash_dates_and_costs():
    r = request(
        decisions=(decision(), decision(day=2, weights={})),
        prices=(price(), price(hour=1), price(day=2), price(day=2, hour=1)),
        config=config(commission_bps=D("100")),
    )
    result = run_usd_price_replay(r)
    assert result.daily.iloc[-1].nav_usd == D("99")
    assert result.daily.iloc[-1].positions_usd == 0
    assert sum(result.daily.costs_usd) == D("1")
    assert result.holdings.iloc[-1].valuation_at == at(2)
    assert len(result.daily) == 3


@pytest.mark.parametrize("same_time", [False, True])
def test_future_sale_cannot_fund_earlier_buy(same_time):
    times = {"A": at(2, 2), "B": at(2, 2) if same_time else at(2, 1)}
    result = run_usd_price_replay(
        request(
            instruments=(instrument("A"), instrument("B")),
            prices=tuple(
                price(name, day=day, hour=hour)
                for name in ("A", "B")
                for day, hour in ((1, 0), (1, 1), (2, 0), (2, 1), (2, 2))
            ),
            decisions=(
                decision(weights={"A": D("1")}, times={"A": at(1, 1), "B": at(1, 1)}),
                decision(day=2, weights={"B": D("1")}, times=times),
            ),
        )
    )
    final = result.daily.iloc[-1]
    assert final.nav_usd == D("100")
    assert final.cash_usd == (D("0") if same_time else D("100"))
    b = result.transactions[result.transactions.instrument_id == "B"].iloc[-1]
    assert b.executed_delta == (D("10") if same_time else D("0"))
    assert b.requested_delta == D("10")


def test_price_and_fx_changes_reconcile_through_sale_and_costs():
    r = request(
        instruments=(instrument(currency="GBP"),),
        prices=(price(), price(hour=1), price(day=2, value="20"), price(day=2, hour=1, value="30")),
        decisions=(decision(weights={"A": D("0.25")}), decision(day=2, weights={})),
        fx=(fx("GBP", "USD", "1.25"), fx("GBP", "USD", "1.5", day=2)),
        config=config(fx_pairs={"GBP": ("GBP", "USD")}, commission_bps=D("100")),
    )
    result = run_usd_price_replay(r)
    assert result.daily.iloc[-1].nav_usd == D("163.85")
    assert sum(result.daily.local_price_pnl_usd) == D("55")
    assert sum(result.daily.fx_pnl_usd) == D("10")
    assert sum(result.daily.costs_usd) == D("1.15")


def test_missing_or_assumed_execution_and_stale_held_marks_fail():
    cases = [
        request(prices=(price(),)),
        request(
            prices=(price(), price(hour=1, availability_basis="assumed_date_lag")),
            config=config(allow_assumed_availability=True),
        ),
        request(config=config(max_price_age=timedelta(hours=2))),
    ]
    for r in cases:
        with pytest.raises(USDValidationError):
            run_usd_price_replay(r)


def test_grid_and_clock_are_checked_before_replay():
    for r in [
        request(valuation_times=(at(2), at(3))),
        request(decisions=(decision(times={"A": at(3)}), decision(day=2))),
        request(config=config(return_basis="total")),
        request(instruments=(replace(instrument(), asset_type="future"),)),
    ]:
        with pytest.raises(USDValidationError):
            run_usd_price_replay(r)


def test_replay_retains_currency_units_and_raw_fx_direction():
    r = request(
        instruments=(instrument(currency="GBP"),),
        fx=(fx("USD", "GBP", "0.8"),),
        config=config(fx_pairs={"GBP": ("USD", "GBP")}),
    )
    result = run_usd_price_replay(r)
    row = result.holdings.iloc[-1]
    assert row.currency == "GBP"
    assert row.price_unit == "currency_per_share"
    assert (row.fx_base_currency, row.fx_quote_currency, row.fx_rate, row.fx_unit) == (
        "USD",
        "GBP",
        D("0.8"),
        "quote_per_base",
    )
    assert result.transactions.iloc[0].currency == "GBP"


def test_assumed_fx_is_never_a_transaction_conversion():
    r = request(
        instruments=(instrument(currency="GBP"),),
        fx=(fx("GBP", "USD", "1.25", availability_basis="assumed_date_lag"),),
        config=config(fx_pairs={"GBP": ("GBP", "USD")}, allow_assumed_availability=True),
    )
    with pytest.raises(USDValidationError):
        run_usd_price_replay(r)


def modeled(name="A", day=1, value="10"):
    from usd_ledger_fixtures import REF

    return USDModeledExecutionPrice(
        name,
        date(2026, 1, day),
        at(day, 1),
        D(value),
        "currency_per_share",
        REF,
        "synthetic-session.v1",
        "synthetic-open.v1",
    )


def test_modeled_reference_replay_uses_exact_open_and_marks_noneligible():
    result = run_usd_price_replay(
        request(
            modeled_execution_prices=(modeled(),),
            config=config(allow_modeled_execution_prices=True),
        )
    )
    transaction = result.transactions.iloc[0]
    assert transaction.local_price == D("10")
    assert transaction.execution_evidence_kind == "modeled_reference"
    assert transaction.modeled_price_session_date == date(2026, 1, 1)
    assert transaction.modeled_price_model_id == "synthetic-open.v1"
    assert bool(transaction.execution_eligible) is False
    assert result.diagnostics["modeled_execution_enabled"] is True
    assert result.summary["orders_submitted"] is False


def test_missing_modeled_reference_never_falls_back_to_daily_close():
    with pytest.raises(USDValidationError, match="modeled execution"):
        run_usd_price_replay(request(config=config(allow_modeled_execution_prices=True)))


def test_modeled_reference_allows_assumed_fx_only_in_opted_in_mode():
    r = request(
        instruments=(instrument(currency="GBP"),),
        fx=(fx("GBP", "USD", "1.25", availability_basis="assumed_market_session"),),
        modeled_execution_prices=(modeled(),),
        config=config(
            fx_pairs={"GBP": ("GBP", "USD")},
            allow_assumed_availability=True,
            allow_modeled_execution_prices=True,
        ),
    )
    result = run_usd_price_replay(r)
    assert result.transactions.iloc[0].fx_availability_basis == "assumed_market_session"
    verified_only = replace(r, config=config(fx_pairs={"GBP": ("GBP", "USD")}))
    with pytest.raises(USDValidationError):
        run_usd_price_replay(verified_only)


def test_modeled_execution_rejects_assumed_date_lag_fx_even_when_opted_in():
    r = request(
        instruments=(instrument(currency="GBP"),),
        fx=(fx("GBP", "USD", "1.25", availability_basis="assumed_date_lag"),),
        modeled_execution_prices=(modeled(),),
        config=config(
            fx_pairs={"GBP": ("GBP", "USD")},
            allow_assumed_availability=True,
            allow_modeled_execution_prices=True,
        ),
    )
    with pytest.raises(USDValidationError, match="availability basis"):
        run_usd_price_replay(r)
