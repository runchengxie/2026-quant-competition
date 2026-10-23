"""Total costs are replayed through holdings, with unchanged policy targets."""

from datetime import date, timedelta

import pytest


def test_cost_replay_changes_holdings_not_only_reported_return():
    from crypto_mm.daily.robustness import replay_robustness
    from crypto_mm.daily.controls import build_control_targets

    data = dict(dates=[(date(2024,1,1)+timedelta(days=i)).isoformat() for i in range(260)],close={"BTCUSDT":[100*(1.002 if i%2 else 1) for i in range(260)]})
    low = replay_robustness(data,"trend200_vol40_strict",fee_bps=35)
    high = replay_robustness(data,"trend200_vol40_strict",fee_bps=50)
    assert high["net"]["periods"][0]["positions"]["BTCUSDT"] < low["net"]["periods"][0]["positions"]["BTCUSDT"]
    strict = build_control_targets(data,"trend200_vol40_strict")["targets"]
    matched = build_control_targets(data,"ew_trend_gross_matched")["targets"]
    assert [sum(t.values()) for t in strict] == [sum(t.values()) for t in matched]
    assert high["gross"] == low["gross"]


@pytest.mark.parametrize("fee",[10,25,True,float("nan")])
def test_only_total_35_or_50_bps_allowed(fee):
    from crypto_mm.daily.robustness import replay_robustness

    with pytest.raises(ValueError):
        replay_robustness({},"ew_trend_gross_matched",fee_bps=fee)


def test_standalone_cli_help_and_rejected_batch(tmp_path):
    import subprocess
    import sys

    module = "crypto_mm.daily.robustness_cli"
    assert subprocess.run([sys.executable,"-m",module,"--help"],capture_output=True,timeout=15).returncode == 0
    invalid = tmp_path / "input.json"
    invalid.write_text('{"schema":"unknown"}')
    child = subprocess.run([sys.executable,"-m",module,"--batch",str(invalid),"--output-root",str(tmp_path / "out")],capture_output=True,timeout=15)
    assert child.returncode == 2
    assert not (tmp_path / "out").exists()
