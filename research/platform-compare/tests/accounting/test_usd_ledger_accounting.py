# Derived from quant-platform 28a32ba707ad72d1eb68cde5075663e1b3819ac7.
# Modified for the competition namespace/identity; licensed under Apache-2.0.
# See accounting/ORIGIN.json and LICENSE-APACHE-2.0.txt for provenance and terms.
import pytest
from usd_ledger_fixtures import D, config, instrument

from platform_compare.accounting.usd_ledger_accounting import settle_usd_rebalance, value_usd_book
from platform_compare.accounting.usd_ledger_models import USDValidationError


def settle(q, cash, desired, *, marks=None, instruments=None, cfg=None, ids=None):
    instruments = instruments or {"A": instrument()}
    marks = marks or {"A": D("10")}
    return settle_usd_rebalance(
        q,
        D(cash),
        desired,
        marks,
        dict.fromkeys(marks, D("1")),
        instruments,
        cfg or config(),
        execution_ids=frozenset(instruments if ids is None else ids),
    )


def test_book_values_quantity_and_cash_without_implicit_rebalance():
    assert value_usd_book({"A": D("2")}, D("70"), {"A": D("10")}, {"A": D("1.5")}) == (
        D("30"),
        D("100"),
    )
    assert value_usd_book({"A": D("2")}, D("70"), {"A": D("20")}, {"A": D("1.5")}) == (
        D("60"),
        D("130"),
    )


def test_buy_and_liquidation_costs_are_debited_once():
    cfg = config(commission_bps=D("100"), fx_cost_bps=D("200"))
    q, cash, trades = settle({}, "100", {"A": D("5")}, cfg=cfg)
    assert q == {"A": D("5")}
    assert cash == D("49.5")
    assert trades.iloc[0].fx_cost_usd == D("0")
    q, cash, trades = settle(q, str(cash), {"A": D("0")}, cfg=cfg)
    assert q["A"] == D("0")
    assert cash == D("99")
    assert trades.iloc[0].commission_usd == D("0.5")


def test_two_buys_scale_proportionally_including_costs():
    q, cash, trades = settle(
        {},
        "100",
        {"A": D("5"), "B": D("2.5")},
        marks={"A": D("10"), "B": D("20")},
        instruments={"A": instrument(), "B": instrument("B")},
        cfg=config(commission_bps=D("100")),
    )
    assert D("0") <= cash < D("0.000000001")
    assert abs(q["A"] - 2 * q["B"]) <= D("0.000000000001")
    assert sum(trades.notional_usd) + sum(trades.costs_usd) + cash == D("100")


def test_integral_lot_and_full_odd_lot_liquidation():
    ins = {"A": instrument(lot=3)}
    q, cash, _ = settle(
        {}, "100", {"A": D("5")}, instruments=ins, cfg=config(sizing_mode="integral")
    )
    assert q["A"] == D("3") and cash == D("70")
    q, cash, _ = settle(
        {"A": D("5")}, "0", {"A": D("0")}, instruments=ins, cfg=config(sizing_mode="integral")
    )
    assert q["A"] == D("0") and cash == D("50")
    q, cash, _ = settle(
        {"A": D("5")}, "0", {"A": D("3")}, instruments=ins, cfg=config(sizing_mode="integral")
    )
    assert q["A"] == D("5") and cash == D("0")


def test_sells_fund_same_batch_buys_and_other_batches_are_untouched():
    ins = {"A": instrument(), "B": instrument("B")}
    marks = {"A": D("10"), "B": D("10")}
    desired = {"A": D("0"), "B": D("5")}
    q, cash, _ = settle({"A": D("5")}, "0", desired, instruments=ins, marks=marks, ids={"B"})
    assert q["A"] == D("5") and q["B"] == D("0") and cash == D("0")
    q, cash, _ = settle({"A": D("5")}, "0", desired, instruments=ins, marks=marks)
    assert q == {"A": D("0"), "B": D("5")} and cash == D("0")


@pytest.mark.parametrize(
    "q,cash,desired",
    [
        ({"A": D("-1")}, "100", {"A": D("0")}),
        ({}, "-1", {"A": D("1")}),
        ({}, "100", {"A": D("-1")}),
    ],
)
def test_negative_inventory_cash_and_oversells_fail(q, cash, desired):
    with pytest.raises(USDValidationError):
        settle(q, cash, desired)


def test_local_currency_trade_has_separate_fx_and_slippage_costs():
    q, cash, t = settle_usd_rebalance(
        {},
        D("100"),
        {"A": D("2")},
        {"A": D("10")},
        {"A": D("1.5")},
        {"A": instrument(currency="GBP")},
        config(commission_bps=D("100"), slippage_bps=D("200"), fx_cost_bps=D("300")),
        execution_ids=frozenset({"A"}),
    )
    assert q["A"] == D("2") and cash == D("68.2")
    assert list(t.iloc[0][["commission_usd", "slippage_usd", "fx_cost_usd"]]) == [
        D("0.3"),
        D("0.6"),
        D("0.9"),
    ]


def test_signed_slippage_moves_buy_and_sell_execution_prices_once():
    cfg = config(commission_bps=D("100"), slippage_bps=D("100"))
    q, cash, buys = settle_usd_rebalance(
        {},
        D("100"),
        {"A": D("2")},
        {"A": D("10")},
        {"A": D("1")},
        {"A": instrument()},
        cfg,
        execution_ids=frozenset({"A"}),
        execution_prices={"A": D("10.1")},
    )
    assert buys.iloc[0].local_price == D("10")
    assert buys.iloc[0].execution_price == D("10.1")
    assert buys.iloc[0].slippage_usd == D("0.2")
    assert cash == D("79.6")
    q, cash, sells = settle_usd_rebalance(
        q,
        cash,
        {"A": D("0")},
        {"A": D("10")},
        {"A": D("1")},
        {"A": instrument()},
        cfg,
        execution_ids=frozenset({"A"}),
        execution_prices={"A": D("9.9")},
    )
    assert sells.iloc[0].local_price == D("10")
    assert sells.iloc[0].execution_price == D("9.9")
    assert sells.iloc[0].slippage_usd == D("0.2")
    assert cash == D("99.2")


def test_integral_affordability_charges_commission_on_reference_not_slipped_price():
    q, cash, trades = settle_usd_rebalance(
        {},
        D("10.2"),
        {"A": D("1")},
        {"A": D("10")},
        {"A": D("1")},
        {"A": instrument()},
        config(commission_bps=D("100"), slippage_bps=D("100")),
        execution_ids=frozenset({"A"}),
        execution_prices={"A": D("10.1")},
    )
    assert q == {"A": D("1")}
    assert cash == D("0")
    assert trades.iloc[0].commission_usd == D("0.1")
