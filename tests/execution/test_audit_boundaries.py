from decimal import Decimal

import pytest

from apps.execution_runner.config import (
    ConfigurationError,
    RunnerSettings,
    resolve_runner_settings,
)
from apps.execution_runner.runner import ExecutionRunner
from packages.contracts import TargetSet
from packages.execution_policies.baseline import OrderIntent, plan_twap
from strategies.nira.handoff import (
    HandoffValidationError,
    NiraTargetHandoff,
    write_target_artifact,
)


@pytest.mark.parametrize(
    "settings",
    [
        {"environment": "live", "live_enabled": False},
        {"environment": "unknown"},
        {"dry_run": "false"},
        {"gateway_port": 0},
    ],
)
def test_direct_settings_cannot_bypass_configuration_invariants(settings):
    with pytest.raises(ConfigurationError):
        RunnerSettings(**settings)


def test_twap_rejects_fractional_units_instead_of_increasing_quantity():
    intent = OrderIntent("AAPL.US", "BUY", Decimal("5.5"), None, "market")
    with pytest.raises(ValueError, match="whole"):
        plan_twap(intent, slices=3)


def test_fractional_gateway_port_is_not_silently_truncated():
    with pytest.raises(ConfigurationError, match="integer"):
        resolve_runner_settings(config={"gateway_port": 4002.5}, environment={})


def test_handoff_alias_rejected_without_touching_existing_artifact(tmp_path):
    handoff = NiraTargetHandoff.from_payload(
        {
            "schema_version": "1.0",
            "strategy_id": "audit",
            "market": "JP",
            "as_of": "2026-09-03T00:00:00Z",
            "targets": [{"symbol": "1321.T", "weight": "1.0", "quantity": "1"}],
        },
        {"strategy_id": "audit", "market": "JP"},
    )
    target = tmp_path / "targets.json"
    target.write_bytes(b"existing artifact")
    alias = tmp_path / "sub" / ".." / "targets.json"
    with pytest.raises(HandoffValidationError, match="different"):
        write_target_artifact(handoff, target, lineage_path=alias, overwrite=True)
    assert target.read_bytes() == b"existing artifact"


@pytest.mark.parametrize("adapter_fails", [False, True])
def test_rebalance_records_each_intent_before_adapter_call(tmp_path, adapter_fails):
    targets = TargetSet.from_dict(
        {
            "schema_version": "1.0",
            "strategy_id": "audit",
            "market": "US",
            "as_of": "2026-09-03T00:00:00Z",
            "targets": [
                {"symbol": "AAPL.US", "weight": "0.5", "quantity": "2"},
                {"symbol": "MSFT.US", "weight": "0.5", "quantity": "3"},
            ],
        }
    )

    class Port:
        def submit(self, candidates):
            raise AssertionError("rebalance must use submit_intents")

        def submit_intents(self, intents):
            events = runner.journal.read()
            assert [event["order_id"] for event in events] == [
                i.order_id for i in intents
            ]
            assert [event["quantity"] for event in events] == ["2", "3"]
            if adapter_fails:
                raise RuntimeError("synthetic partial submission failure")

    runner = ExecutionRunner(
        RunnerSettings(), submission_port=Port(), journal_path=tmp_path / "events.jsonl"
    )
    result = runner.run_rebalance(targets, {})
    assert result.status == ("unknown" if adapter_fails else "submitted")
    assert (
        len([e for e in runner.journal.read() if e["kind"] == "order_submitted"]) == 2
    )


def test_rebalance_does_not_call_adapter_if_journal_fails(tmp_path, monkeypatch):
    targets = TargetSet.from_dict(
        {
            "schema_version": "1.0",
            "strategy_id": "audit",
            "market": "US",
            "as_of": "2026-09-03T00:00:00Z",
            "targets": [{"symbol": "AAPL.US", "weight": "1.0", "quantity": "2"}],
        }
    )

    class Port:
        def submit(self, candidates):
            raise AssertionError("rebalance must use submit_intents")

        called = False

        def submit_intents(self, intents):
            self.called = True

    port = Port()
    runner = ExecutionRunner(
        RunnerSettings(), submission_port=port, journal_path=tmp_path / "events.jsonl"
    )

    def fail(event):
        raise OSError("synthetic durable write failure")

    monkeypatch.setattr(runner.journal, "append", fail)
    with pytest.raises(OSError, match="durable write"):
        runner.run_rebalance(targets, {})
    assert not port.called
