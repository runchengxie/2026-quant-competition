"""The synthetic daily producer never invokes maker or broker code."""

import math
from datetime import date, timedelta

import pytest

from crypto_mm.workflow import run_workflow


def job():
    dates = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(270)]
    prices = {
        "DEMO_A_USDT": [100 + i / 10 + math.sin(i / 5) for i in range(270)],
        "DEMO_B_USDT": [120 - i / 20 + math.cos(i / 7) for i in range(270)],
    }
    return dict(
        schema="competition.workflow_job.v1",
        project="crypto-mm",
        synthetic=True,
        parameters=dict(
            initial_equity=1,
            fee_bps=35,
            quote_currency="USDT",
            arm_id="trend200_vol40_strict",
            decision_schedule="weekly_monday",
        ),
        data=dict(dates=dates, close=prices),
    )


def test_synthetic_workflow_respects_hold_days_and_reports_actual_environment(tmp_path):
    value = run_workflow(job(), tmp_path / "run")
    assert value["schema"] == "competition.workflow_leaf_result.v1"
    assert value["accounting_model"] == "self_financing_daily.v1"
    assert value["quote_currency"] == "USDT"
    assert len(value["code_sha256"]) == 64
    assert value["environment"]["python"].startswith("3.12.")
    assert len(value["evidence"]["net"]["periods"]) == 18
    assert any(p["cost"] == 0 for p in value["evidence"]["net"]["periods"][1:])
    assert all(p["cost"] == 0 for p in value["evidence"]["gross"]["periods"])
    assert {r["path"] for r in value["artifacts"]} == {
        "prices.json",
        "targets.json",
        "net.json",
        "gross.json",
        "summary.json",
    }
    with pytest.raises(FileExistsError):
        run_workflow(job(), tmp_path / "run")


@pytest.mark.parametrize(
    "mutation", ["real", "wrong_project", "bad_currency", "real_symbol"]
)
def test_workflow_rejects_non_synthetic_or_mismatched_jobs(tmp_path, mutation):
    value = job()
    if mutation == "real":
        value["synthetic"] = 1
    if mutation == "wrong_project":
        value["project"] = "equity-lab"
    if mutation == "bad_currency":
        value["parameters"]["quote_currency"] = "USD"
    if mutation == "real_symbol":
        value["data"]["close"]["BTCUSDT"] = value["data"]["close"].pop("DEMO_A_USDT")
    with pytest.raises(ValueError):
        run_workflow(value, tmp_path / "run")
    assert not (tmp_path / "run").exists()
