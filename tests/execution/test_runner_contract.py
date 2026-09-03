from __future__ import annotations

import importlib.util

import apps.execution_runner.config as runner_config
import pytest

from adapters.nautilus import describe_nautilus_runtime
from apps.execution_runner.config import ConfigurationError, RunnerSettings
from apps.execution_runner.runner import ExecutionRunner
from packages.contracts import TargetSet


def test_execution_runner_configuration_module_is_exposed() -> None:
    """The runner must expose a configuration boundary before brokers are added."""

    assert importlib.util.find_spec("apps.execution_runner.config") is not None


def test_runner_settings_are_exposed() -> None:
    """The execution boundary owns a typed settings object."""

    assert hasattr(runner_config, "RunnerSettings")


def test_runner_settings_resolver_is_exposed() -> None:
    """Settings must be resolved from a controlled configuration boundary."""

    assert callable(getattr(runner_config, "resolve_runner_settings", None))


def test_runner_defaults_to_paper_gateway() -> None:
    """An unset runner must target the local Paper Gateway, never Live."""

    settings = runner_config.resolve_runner_settings()

    assert getattr(settings, "environment", None) == "paper"


def test_runner_defaults_use_local_paper_gateway_parameters() -> None:
    settings = runner_config.resolve_runner_settings()

    assert getattr(settings, "gateway_host", None) == "127.0.0.1"


def test_environment_overrides_config_without_changing_safe_paper_default() -> None:
    settings = runner_config.resolve_runner_settings(
        config={"gateway_host": "gateway.internal", "gateway_port": 4001},
        environment={
            "COMPETITION_EXECUTION_GATEWAY_PORT": "4002",
            "COMPETITION_EXECUTION_DRY_RUN": "true",
        },
    )

    assert settings.environment == "paper"
    assert settings.gateway_host == "gateway.internal"
    assert settings.gateway_port == 4002
    assert settings.dry_run is True


def test_live_mode_requires_two_explicit_environment_guards() -> None:
    with pytest.raises(ConfigurationError, match="live execution requires"):
        runner_config.resolve_runner_settings(
            environment={"COMPETITION_EXECUTION_ENVIRONMENT": "live"}
        )

    settings = runner_config.resolve_runner_settings(
        environment={
            "COMPETITION_EXECUTION_ENVIRONMENT": "live",
            "COMPETITION_EXECUTION_LIVE_ENABLED": "true",
            "COMPETITION_EXECUTION_LIVE_CONFIRMATION": "ENABLE_LIVE_TRADING",
        }
    )

    assert settings.environment == "live"
    assert settings.live_enabled is True


def test_invalid_boolean_or_gateway_port_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="boolean"):
        runner_config.resolve_runner_settings(
            environment={"COMPETITION_EXECUTION_DRY_RUN": "sometimes"}
        )

    with pytest.raises(ConfigurationError, match="gateway_port"):
        runner_config.resolve_runner_settings(
            environment={"COMPETITION_EXECUTION_GATEWAY_PORT": "99999"}
        )


def test_dry_run_never_calls_submission_port() -> None:
    class RecordingPort:
        called = False

        def submit(self, candidates: object) -> None:
            self.called = True
            raise AssertionError(f"dry-run attempted to submit {candidates!r}")

    target_set = TargetSet.from_dict(
        {
            "schema_version": "1.0",
            "strategy_id": "japanese-nira",
            "market": "JP",
            "as_of": "2026-09-03T00:00:00Z",
            "targets": [{"symbol": "1321.T", "weight": "1.0", "quantity": "1"}],
        }
    )
    port = RecordingPort()
    runner = ExecutionRunner(
        RunnerSettings(dry_run=True),
        submission_port=port,
    )

    result = runner.run(target_set)

    assert result.status == "dry_run"
    assert result.submitted is False
    assert result.broker_call_attempted is False
    assert [candidate.symbol for candidate in result.candidates] == ["1321.T"]
    assert port.called is False


def test_runner_blocks_non_dry_run_until_a_real_adapter_is_installed() -> None:
    target_set = TargetSet.from_dict(
        {
            "schema_version": "1.0",
            "strategy_id": "japanese-nira",
            "market": "JP",
            "as_of": "2026-09-03T00:00:00Z",
            "targets": [{"symbol": "1321.T", "weight": "1.0", "quantity": "1"}],
        }
    )

    result = ExecutionRunner(RunnerSettings()).run(target_set)

    assert result.status == "blocked"
    assert result.submitted is False
    assert result.broker_call_attempted is False
    assert "Task 4" in result.message


def test_nautilus_dependency_is_optional_and_described_without_import_failure() -> None:
    status = describe_nautilus_runtime()

    assert isinstance(status.available, bool)
    assert isinstance(status.message, str)
