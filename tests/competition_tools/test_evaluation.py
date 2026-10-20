import pytest

from competition_tools.evaluation.matrix import equity_folds
from competition_tools.evaluation.publication import public_snapshot


def test_equity_folds_require_252_warmup_and_complete_63_session_window():
    dates = [f"session-{i:04}" for i in range(314)]
    assert equity_folds(dates) == []
    dates.append("session-0314")
    assert equity_folds(dates) == [
        {"warmup_start": "session-0000", "start": "session-0252", "end": "session-0314"}
    ]


def test_projection_excludes_private_artifacts_and_nonfinite_metrics():
    result = {
        "schema": "competition.crypto_daily_result.v1",
        "strategy": "equal_weight",
        "net_return": 0.1,
        "gross_return": 0.11,
        "max_drawdown": 0.2,
        "sharpe": 1,
        "turnover": 1,
        "mean_exposure": 1,
        "start": "2024-01-01",
        "end": "2024-12-31",
        "quote_currency": "USDT",
        "fee_bps": 10,
        "products": ["BTCUSDT", "ETHUSDT"],
        "universe_status": "fixed_current",
        "periods_per_year": 365,
        "account": "private-account-sentinel",
        "periods": [{"raw": "licensed-bar-sentinel"}],
        "credential_file": "C:/private/key",
        "manifest_path": "D:/private/input",
    }
    value = public_snapshot(
        {
            "daily_results": [result],
            "coverage": [],
            "blockers": ["PIT_MEMBERSHIP_MISSING"],
        }
    )
    assert value["daily_results"][0]["net_return"] == 0.1
    assert "private" not in str(value)
    assert "licensed-bar-sentinel" not in str(value)
    with pytest.raises(ValueError):
        public_snapshot(
            {
                "daily_results": [result | {"net_return": float("nan")}],
                "coverage": [],
                "blockers": [],
            }
        )


def test_projection_separates_unknown_maker_currency_and_equity_diagnostics():
    equity = {
        "market": "HK",
        "strategy": "equal_weight",
        "fold": 0,
        "status": "completed",
        "start": "2024-01-01",
        "end": "2024-03-31",
        "universe_count": 1,
        "cost_bps": 30,
        "quote_currency": "HKD",
        "net_return": 0.1,
        "sharpe": 1,
        "max_drawdown": 0.2,
        "turnover": 1,
        "mean_exposure": 1,
        "sessions": 63,
        "input_hashes": {"private": "secret"},
    }
    maker = {
        "strategy_id": "B0",
        "scenario": "fee_1bps",
        "metrics": {"total_pnl": -347.0, "fill_count": 5400},
        "quote_currency": None,
        "days": ["2026-03-19", "2026-03-20", "2026-03-21"],
    }
    value = public_snapshot(
        {
            "daily_results": [],
            "coverage": [],
            "blockers": [],
            "equity_results": [equity],
            "maker_results": [maker],
        }
    )
    assert value["maker_results"][0]["quote_currency"] is None
    assert value["equity_results"][0]["universe_count"] == 1
    assert "private" not in str(value)


def test_evaluation_spec_schema_rejects_relative_manifests():
    import json
    from pathlib import Path
    from jsonschema import Draft202012Validator

    root = Path(__file__).resolve().parents[2]
    schema = json.loads(
        (root / "schemas/research/evaluation-spec.v1.schema.json").read_text()
    )
    validator = Draft202012Validator(schema)
    assert list(
        validator.iter_errors(
            {"schema": "competition.evaluation_spec.v1", "manifests": ["relative.json"]}
        )
    )
    assert not list(
        validator.iter_errors(
            {
                "schema": "competition.evaluation_spec.v1",
                "manifests": ["/absolute/manifest.json"],
            }
        )
    )
