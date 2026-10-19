"""Retain actual legacy allocation decisions without adding a second lag."""

from dataclasses import asdict
import hashlib
import json

import pandas as pd
import pytest

from equity_lab.accounting_export import export_decisions
from equity_lab.backtest.engine import BacktestConfig, run_equal_weight_backtest


def frame():
    return pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "code": ["US.DEMO_A"] * 3,
            "close": [10.0, 11.0, 12.0],
            "signal": [1.0, 0.0, 1.0],
        }
    )


def test_actual_target_decisions_keep_single_signal_lag_and_report_bytes():
    source = frame()
    cfg = BacktestConfig(initial_capital=100.0, commission_bps=0.0, slippage_bps=0.0)
    portfolio, detail = run_equal_weight_backtest(source, cfg)
    before = portfolio.to_csv(index=False).encode()
    exported = export_decisions(
        source,
        cfg,
        strategy_id="equal_weight",
        market="US",
        synthetic=True,
        input_fingerprint="a" * 64,
    )
    assert [row["weights"] for row in exported["decisions"]] == [
        {"US.DEMO_A": "1"},
        {"US.DEMO_A": "0"},
    ]
    assert [(r["source_date"], r["execution_date"]) for r in exported["decisions"]] == [
        ("2026-01-01", "2026-01-02"),
        ("2026-01-02", "2026-01-03"),
    ]
    assert exported["legacy"]["final_nav"] == str(float(portfolio.iloc[-1]["equity"]))
    assert portfolio.to_csv(index=False).encode() == before
    assert exported["legacy_config"] == asdict(cfg)
    assert (
        exported["legacy_config_fingerprint"]
        == hashlib.sha256(
            json.dumps(
                asdict(cfg),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode()
        ).hexdigest()
    )
    pd.testing.assert_frame_equal(source, frame())


def test_turnover_limited_target_is_not_replaced_with_raw_signal():
    cfg = BacktestConfig(
        initial_capital=100.0,
        commission_bps=1.0,
        slippage_bps=2.0,
        max_daily_turnover=0.25,
    )
    out = export_decisions(
        frame(),
        cfg,
        strategy_id="momentum_20d",
        market="US",
        synthetic=True,
        input_fingerprint="b" * 64,
    )
    assert out["decisions"][0]["weights"] == {"US.DEMO_A": "0.25"}
    assert out["legacy"]["commission_bps"] == "1"
    assert out["legacy"]["slippage_bps"] == "2"


@pytest.mark.parametrize(
    "mutation", ["duplicate", "unbalanced", "nonfinite", "dividend"]
)
def test_unsupported_or_ambiguous_frames_rejected(mutation):
    source = frame()
    if mutation == "duplicate":
        source = pd.concat([source, source.iloc[[0]]])
    if mutation == "unbalanced":
        source = pd.concat(
            [
                source,
                pd.DataFrame(
                    {
                        "date": ["2026-01-01"],
                        "code": ["US.DEMO_B"],
                        "close": [1.0],
                        "signal": [1.0],
                    }
                ),
            ]
        )
    if mutation == "nonfinite":
        source.loc[0, "close"] = float("inf")
    if mutation == "dividend":
        source["dividend"] = 1.0
    with pytest.raises(ValueError):
        export_decisions(
            source,
            BacktestConfig(),
            strategy_id="equal_weight",
            market="US",
            synthetic=True,
            input_fingerprint="a" * 64,
        )


def test_all_cash_and_no_next_session_do_not_invent_execution():
    source = frame()
    source["signal"] = 0.0
    out = export_decisions(
        source,
        BacktestConfig(),
        strategy_id="equal_weight",
        market="US",
        synthetic=True,
        input_fingerprint="a" * 64,
    )
    assert all(set(row["weights"].values()) == {"0"} for row in out["decisions"])
    assert len(out["decisions"]) == 2
    assert out["legacy"]["final_nav"] == "100000.0"


def test_synthetic_cli_uses_actual_strategy_and_refuses_overwrite(tmp_path):
    import os
    import subprocess
    import sys
    import json

    args = [
        sys.executable,
        "-m",
        "equity_lab.accounting_export",
        "--synthetic-demo",
        "--market",
        "US",
        "--strategy",
        "momentum_20d",
        "--output-root",
        str(tmp_path / "demo"),
    ]
    result = subprocess.run(args, capture_output=True, text=True, env=os.environ.copy())
    assert result.returncode == 0, result.stderr
    export = json.loads((tmp_path / "demo/legacy.json").read_text())
    assert export["synthetic"] is True
    assert export["strategy_id"] == "momentum_20d"
    assert set(export["decisions"][0]["weights"].values()) == {"0"}
    assert "0.5" in set(export["decisions"][-1]["weights"].values())
    again = subprocess.run(args, capture_output=True, text=True)
    assert again.returncode == 2
    assert "Traceback" not in again.stdout + again.stderr
