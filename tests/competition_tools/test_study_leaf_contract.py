"""Consumer rejects financially incomplete or mismatched child results."""

import json
import pytest
from competition_tools.datasets.storage import digest
from competition_tools.evaluation.study_runner import _result


def result_fixture(tmp_path):
    job = dict(
        job_id="a" * 64,
        plan_sha256="b" * 64,
        manifest_sha256="c" * 64,
        market="US",
        quote_currency="USD",
        strategy="equal_weight",
        fee_bps=20,
        products=["A"],
        expected_leaf_sha256="d" * 64,
        code_commit="e" * 40,
        parameters={},
        benchmark="SPY",
        fold={"start": "2024-01-01", "end": "2024-03-31", "scoring_periods": 63},
    )
    artifact = tmp_path / "periods.json"
    artifact.write_text("{}")
    metrics = dict(
        periods=63,
        net_return=0.0,
        gross_return=0.0,
        cost_drag=0.0,
        volatility=0.0,
        sharpe=None,
        max_drawdown=0.0,
        turnover=1.0,
        total_costs=0.0,
        mean_daily_turnover=1 / 63,
        mean_exposure=1.0,
        flat_days=0,
    )
    value = {
        k: job[k]
        for k in (
            "job_id",
            "plan_sha256",
            "manifest_sha256",
            "market",
            "quote_currency",
            "strategy",
            "fee_bps",
            "products",
            "code_commit",
            "parameters",
            "benchmark",
            "fold",
        )
    }
    value.update(
        schema="competition.daily_study_result.v1",
        code_sha256=job["expected_leaf_sha256"],
        start=job["fold"]["start"],
        end=job["fold"]["end"],
        accepted_research=False,
        methods=dict(
            method_id="us.equal_weight.self_financing_daily.v1",
            strategy="equal_weight",
            signal_parameters={},
            signal_lag_periods=1,
            rebalance="daily_target_weights",
            execution_assumption="lagged_close_proxy",
            warmup_periods=252,
            scoring_periods=63,
            fold_initialization="independent_cash",
            cost_model="self_financing_oneway_bps",
            terminal_liquidation=False,
            retrospective=True,
        ),
        metrics=metrics,
        artifacts=[dict(path="periods.json", sha256=digest(artifact), bytes=2)],
    )
    return job, value


@pytest.mark.parametrize(
    "mutation",
    ["missing_metric", "boolean_metric", "exposure", "commit", "benchmark", "method"],
)
def test_invalid_child_contract(tmp_path, mutation):
    job, value = result_fixture(tmp_path)
    if mutation == "missing_metric":
        value["metrics"].pop("net_return")
    elif mutation == "boolean_metric":
        value["metrics"]["net_return"] = True
    elif mutation == "exposure":
        value["metrics"]["mean_exposure"] = 2
    elif mutation == "commit":
        value["code_commit"] = "f" * 40
    elif mutation == "benchmark":
        value["benchmark"] = "OTHER"
    else:
        value["methods"]["signal_lag_periods"] = 0
    (tmp_path / "result.json").write_text(json.dumps(value))
    with pytest.raises(ValueError, match="INVALID_STUDY_RESULT"):
        _result(job, tmp_path)


def test_valid_child_contract(tmp_path):
    job, value = result_fixture(tmp_path)
    (tmp_path / "result.json").write_text(json.dumps(value))
    assert _result(job, tmp_path)[0] == value
