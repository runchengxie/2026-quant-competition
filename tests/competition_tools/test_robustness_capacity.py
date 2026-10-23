"""Capacity is an ex-post assumption check, not an execution promise."""

import copy

import pytest


def example():
    quantity = 0.009965122072745391
    periods = dict(prices=dict(dates=["2025-01-01","2025-01-02","2025-01-03"],close={"BTCUSDT":[100.,110.,100.]}),net=[dict(date="2025-01-02",positions={"BTCUSDT":quantity*110},equity=quantity*110,turnover=quantity*100),dict(date="2025-01-03",positions={"BTCUSDT":quantity*100},equity=quantity*100,turnover=0.)])
    return dict(job_id="a"*64,market="crypto",products=["BTCUSDT"]), periods


def test_capacity_uses_actual_trade_units_and_keeps_account_unchanged():
    from competition_tools.evaluation.robustness.capacity import capacity_diagnostics

    job, periods = example()
    original = copy.deepcopy(periods)
    result = capacity_diagnostics(job,periods,{"BTCUSDT":[100.,200.,300.]})
    assert len(result["checks"]) == 6
    first = result["checks"][0]
    assert first["notional_usdt"] == 10000
    assert first["max_participation"] == pytest.approx(0.9965122072745391)
    assert first["breach_days"] == 1
    assert first["execution_eligible"] is False
    assert first["ex_post"] is True
    assert periods == original


def test_missing_or_zero_volume_is_unavailable_not_zero_participation():
    from competition_tools.evaluation.robustness.capacity import capacity_diagnostics

    job, periods = example()
    for volumes in ({},{"BTCUSDT":[0.,200.,300.]}):
        result = capacity_diagnostics(job,periods,volumes)
        assert all(r["unavailable_days"]==1 for r in result["checks"])
        assert all(r["status"]=="incomplete_volume" for r in result["checks"])


def test_turnover_mismatch_is_rejected():
    from competition_tools.evaluation.robustness.capacity import capacity_diagnostics

    job, periods = example()
    periods["net"][0]["turnover"] = 0.
    with pytest.raises(ValueError,match="TURNOVER"):
        capacity_diagnostics(job,periods,{"BTCUSDT":[100.,200.,300.]})
