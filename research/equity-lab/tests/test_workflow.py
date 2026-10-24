"""An explicitly synthetic producer connects the installed equity modules."""

from datetime import date, timedelta

import pytest

from equity_lab.workflow import run_workflow


def job():
    dates = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(24)]
    rows = [
        dict(
            date=day,
            code=code,
            open=100 + drift * i,
            high=101 + drift * i,
            low=99 + drift * i,
            close=100 + drift * i,
            volume=100.0,
        )
        for code, drift in (("US.DEMO_A", 0.5), ("US.DEMO_B", -0.2))
        for i, day in enumerate(dates)
        if not (code == "US.DEMO_A" and i == 6)
    ]
    return dict(
        schema="competition.workflow_job.v1",
        project="equity-lab",
        synthetic=True,
        parameters=dict(
            initial_equity=100,
            fee_bps=20,
            quote_currency="USD",
            short_window=3,
            long_window=5,
        ),
        data=dict(dates=dates, rows=rows),
    )


def test_synthetic_workflow_produces_replay_metrics_and_inspectable_tables(tmp_path):
    output = tmp_path / "run"
    value = run_workflow(job(), output)
    assert value["schema"] == "competition.workflow_leaf_result.v1"
    assert value["synthetic"] is True
    assert value["accounting_model"] == "equity_fractional_proxy.v1"
    assert len(value["code_sha256"]) == 64
    assert len(value["evidence"]["portfolio"]) == 24
    assert value["metrics"]["trading_days"] == 24
    assert {r["path"] for r in value["artifacts"]} == {
        "prepared.csv",
        "signals.csv",
        "portfolio.csv",
        "positions.csv",
        "gross-portfolio.csv",
        "summary.json",
    }
    assert (output / "result.json").is_file()
    with pytest.raises(FileExistsError):
        run_workflow(job(), output)


@pytest.mark.parametrize(
    "mutation", ["real", "wrong_project", "bad_cost", "real_symbol"]
)
def test_workflow_rejects_unapproved_job_shapes_before_creating_output(
    tmp_path, mutation
):
    value = job()
    if mutation == "real":
        value["synthetic"] = False
    if mutation == "wrong_project":
        value["project"] = "crypto-mm"
    if mutation == "bad_cost":
        value["parameters"]["fee_bps"] = float("nan")
    if mutation == "real_symbol":
        value["data"]["rows"][0]["code"] = "US.AAPL"
    with pytest.raises(ValueError):
        run_workflow(value, tmp_path / "run")
    assert not (tmp_path / "run").exists()
