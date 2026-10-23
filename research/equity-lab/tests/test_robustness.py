"""Fixed-pool diagnostics preserve accounting and ignore excluded prices."""

from datetime import date, timedelta

import pytest

STOCKS = "AAPL MSFT AMZN GOOGL META NVDA JPM JNJ XOM PG".split()


def bars():
    return dict(
        dates=[(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(260)],
        close={p: [100.0] * 260 for p in STOCKS},
    )


def test_subset_ignores_excluded_prices_and_funds_initial_fee():
    from equity_lab.study.robustness import evaluate_robustness

    data = bars()
    result = evaluate_robustness(data, "exclude_nvda", fee_bps=20)
    assert result["metrics"]["net_return"] == pytest.approx(1 / 1.002 - 1, abs=1e-12)
    assert "NVDA" not in result["net"]["periods"][0]["positions"]
    data["close"]["NVDA"] = [1 + i**2 for i in range(260)]
    assert evaluate_robustness(data, "exclude_nvda", fee_bps=20) == result


def test_full_pool_matches_original_and_future_does_not_change_past():
    from equity_lab.study.robustness import evaluate_robustness
    from equity_lab.study.controls import evaluate_control

    data = bars()
    assert evaluate_robustness(data, "full_pool", fee_bps=40) == evaluate_control(
        data, "ew_monthly", fee_bps=40, quote_currency="USD"
    )
    before = evaluate_robustness(data, "fixed_six", fee_bps=40)
    data["close"]["AAPL"][-1] = 200
    after = evaluate_robustness(data, "fixed_six", fee_bps=40)
    assert before["net"]["periods"][:-1] == after["net"]["periods"][:-1]


@pytest.mark.parametrize(
    "pool,fee", [("unknown", 20), ("fixed_six", 35), ("exclude_three", True)]
)
def test_invalid_grid_rejected(pool, fee):
    from equity_lab.study.robustness import evaluate_robustness

    with pytest.raises(ValueError):
        evaluate_robustness(bars(), pool, fee_bps=fee)


def test_standalone_cli_help_and_rejected_batch(tmp_path):
    import subprocess
    import sys

    module = "equity_lab.study.robustness_cli"
    assert (
        subprocess.run(
            [sys.executable, "-m", module, "--help"], capture_output=True, timeout=15
        ).returncode
        == 0
    )
    invalid = tmp_path / "input.json"
    invalid.write_text('{"schema":"unknown"}')
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            module,
            "--batch",
            str(invalid),
            "--output-root",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        timeout=15,
    )
    assert child.returncode == 2
    assert not (tmp_path / "out").exists()
