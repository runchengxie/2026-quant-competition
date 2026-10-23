"""The reference solves fee funding analytically, independently of producers."""

import pytest


def test_initial_entry_and_complete_exit_are_self_financing():
    from competition_tools.evaluation.robustness.reference import reference_account

    prices = dict(dates=["2025-01-01","2025-01-02","2025-01-03"],close={"A":[100.,100.,100.]})
    periods = reference_account(prices,[{"A":1.},{}],fee_bps=20)
    assert periods[0]["equity"] == pytest.approx(1/1.002,abs=1e-12)
    assert periods[0]["positions"]["A"] == pytest.approx(1/1.002,abs=1e-12)
    assert periods[1]["equity"] == pytest.approx(.998/1.002,abs=1e-12)
    assert periods[1]["positions"]["A"] == 0


def test_reference_never_sells_at_terminal_window_boundary():
    from competition_tools.evaluation.robustness.reference import reference_account

    prices = dict(dates=["2025-01-01","2025-01-02"],close={"SPY":[100.,110.]})
    periods = reference_account(prices,[{"SPY":1.}],fee_bps=40)
    assert len(periods) == 1
    assert periods[-1]["equity"] == pytest.approx(1.1/1.004,abs=1e-12)
    assert periods[-1]["cost"] == pytest.approx(.004/1.004,abs=1e-12)


def test_reference_rejects_nonfinite_or_unfunded_weights():
    from competition_tools.evaluation.robustness.reference import reference_account

    prices = dict(dates=["2025-01-01","2025-01-02"],close={"A":[100.,100.]})
    for targets in ([{"A":float("nan")}],[{"A":1.1}]):
        with pytest.raises(ValueError):
            reference_account(prices,targets,fee_bps=20)


def test_reference_policy_is_lagged_and_volume_independent():
    from competition_tools.evaluation.robustness.reference import reference_targets
    from datetime import date,timedelta

    data=dict(dates=[(date(2024,1,1)+timedelta(days=i)).isoformat() for i in range(260)],close={"BTCUSDT":[100*(1.002 if i%2 else 1) for i in range(260)]})
    job=dict(market="crypto",input_job=dict(arm_id="trend200_vol40_strict"))
    targets=reference_targets(job,data)
    assert targets[0]=={"BTCUSDT":1.0}
    data["close"]["BTCUSDT"][-1]=100000
    assert reference_targets(job,data)==targets
