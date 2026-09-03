"""Configuration for the broker-neutral execution runner."""

from dataclasses import dataclass
import os
from typing import Mapping


class ConfigurationError(ValueError):
    """Raised when runner configuration would weaken execution safety."""


_LIVE_CONFIRMATION = "ENABLE_LIVE_TRADING"


@dataclass(frozen=True, slots=True)
class RunnerSettings:
    """Resolved, safe execution-runner settings."""

    environment: str = "paper"
    gateway_host: str = "127.0.0.1"
    gateway_port: int = 4002
    client_id: int = 7310
    dry_run: bool = False
    live_enabled: bool = False


def resolve_runner_settings(
    *,
    config: Mapping[str, object] | None = None,
    environment: Mapping[str, str] | None = None,
) -> RunnerSettings:
    """Resolve settings with environment precedence and Paper-safe defaults.

    ``config`` may carry non-secret deployment settings.  Environment values
    override it, which makes local Paper execution explicit and reproducible.
    Live mode deliberately cannot be enabled by config alone: it needs both a
    dedicated environment switch and a literal acknowledgement.
    """

    config = config or {}
    environment = environment if environment is not None else os.environ

    runner_environment = _string_value(
        environment,
        "COMPETITION_EXECUTION_ENVIRONMENT",
        config.get("environment", "paper"),
    ).lower()
    if runner_environment not in {"paper", "live"}:
        raise ConfigurationError("environment must be either 'paper' or 'live'")

    default_port = 4001 if runner_environment == "live" else 4002
    gateway_host = _string_value(
        environment,
        "COMPETITION_EXECUTION_GATEWAY_HOST",
        config.get("gateway_host", "127.0.0.1"),
    )
    if not gateway_host:
        raise ConfigurationError("gateway_host must not be empty")

    gateway_port = _integer_value(
        environment,
        "COMPETITION_EXECUTION_GATEWAY_PORT",
        config.get("gateway_port", default_port),
        field="gateway_port",
        minimum=1,
        maximum=65535,
    )
    client_id = _integer_value(
        environment,
        "COMPETITION_EXECUTION_CLIENT_ID",
        config.get("client_id", 7310),
        field="client_id",
        minimum=0,
        maximum=2_147_483_647,
    )
    dry_run = _boolean_value(
        environment,
        "COMPETITION_EXECUTION_DRY_RUN",
        config.get("dry_run", False),
    )

    live_enabled = False
    if runner_environment == "live":
        live_switch = _boolean_value(
            environment,
            "COMPETITION_EXECUTION_LIVE_ENABLED",
            False,
        )
        confirmation = environment.get("COMPETITION_EXECUTION_LIVE_CONFIRMATION", "")
        if not live_switch or confirmation != _LIVE_CONFIRMATION:
            raise ConfigurationError(
                "live execution requires COMPETITION_EXECUTION_LIVE_ENABLED=true "
                f"and COMPETITION_EXECUTION_LIVE_CONFIRMATION={_LIVE_CONFIRMATION}"
            )
        live_enabled = True

    return RunnerSettings(
        environment=runner_environment,
        gateway_host=gateway_host,
        gateway_port=gateway_port,
        client_id=client_id,
        dry_run=dry_run,
        live_enabled=live_enabled,
    )


def _string_value(
    environment: Mapping[str, str], key: str, default: object
) -> str:
    value = environment.get(key, default)
    if not isinstance(value, str):
        raise ConfigurationError(f"{key} must be a string")
    return value.strip()


def _integer_value(
    environment: Mapping[str, str],
    key: str,
    default: object,
    *,
    field: str,
    minimum: int,
    maximum: int,
) -> int:
    raw = environment.get(key, default)
    if isinstance(raw, bool):
        raise ConfigurationError(f"{field} must be an integer")
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{field} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{field} must be between {minimum} and {maximum}")
    return value


def _boolean_value(
    environment: Mapping[str, str], key: str, default: object
) -> bool:
    raw = environment.get(key, default)
    if isinstance(raw, bool):
        return raw
    if not isinstance(raw, str):
        raise ConfigurationError(f"{key} must be a boolean")
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{key} must be a boolean")

    return RunnerSettings()
