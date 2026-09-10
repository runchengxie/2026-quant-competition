import json
from decimal import Decimal

from apps.execution_runner.preflight import run_preflight


def _write_inputs(tmp_path, *, dry_run=True, weights=("0.5", "0.48")):
    target = {
        "schema_version": "1.0",
        "strategy_id": "hk-baseline",
        "market": "HK",
        "as_of": "2026-09-10T00:00:00Z",
        "targets": [{"symbol": f"07{index:02d}.HK", "weight": weight, "quantity": "100"} for index, weight in enumerate(weights)],
    }
    config = {"market": "HK", "portfolio": {"max_single_weight": 0.6}, "execution": {"environment": "paper", "dry_run": dry_run, "gateway_host": "127.0.0.1", "gateway_port": 4002}}
    target_path = tmp_path / "targets.json"
    config_path = tmp_path / "config.json"
    target_path.write_text(json.dumps(target), encoding="utf-8")
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return target_path, config_path


def test_preflight_passes_local_checks_without_gateway_call(tmp_path):
    target_path, config_path = _write_inputs(tmp_path)
    report = run_preflight(target_path, config_path, check_gateway=False, positions={"0700.HK": Decimal("0")})

    assert report.overall == "pass"
    assert report.check("execution_safety").status == "pass"
    assert report.check("dry_run_rebalance").status == "pass"
    assert report.check("gateway").status == "skipped"


def test_preflight_fails_when_dry_run_is_disabled(tmp_path):
    target_path, config_path = _write_inputs(tmp_path, dry_run=False)
    report = run_preflight(target_path, config_path, check_gateway=False)

    assert report.overall == "fail"
    assert report.check("execution_safety").status == "fail"
    assert report.check("dry_run_rebalance").status == "skipped"


def test_preflight_fails_when_target_exceeds_configured_single_weight(tmp_path):
    target_path, config_path = _write_inputs(tmp_path, weights=("0.7", "0.28"))
    report = run_preflight(target_path, config_path, check_gateway=False)

    assert report.overall == "fail"
    assert report.check("target_risk").status == "fail"


def test_preflight_report_is_json_serializable(tmp_path):
    target_path, config_path = _write_inputs(tmp_path)
    report = run_preflight(target_path, config_path, check_gateway=False)

    payload = report.to_dict()
    assert payload["overall"] == "pass"
    assert json.loads(json.dumps(payload))["checks"]


def test_preflight_marks_gateway_unreachable_without_order_attempt(tmp_path):
    target_path, config_path = _write_inputs(tmp_path)
    report = run_preflight(target_path, config_path, check_gateway=True, gateway_timeout=0.01)

    assert report.check("gateway").status in {"pass", "blocked"}
    assert report.check("dry_run_rebalance").status == "pass"
