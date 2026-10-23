"""Offline preparation, with no broker-session import or service activation."""

from datetime import datetime, timezone

from ..evaluation.observation_preparation import prepare_observation, prepare_us_refresh
from .processes import envelope


def execute(operation, config, manifest, output, *, parent_registry=None):
    if operation == "us-refresh":
        value = prepare_us_refresh(config, manifest, datetime.now(timezone.utc), output)
    elif operation == "market" and parent_registry:
        value = prepare_observation(config, manifest, output, parent_registry=parent_registry)
    else:
        raise ValueError("PREPARATION_ARGUMENTS_REQUIRED")
    return envelope("observation-prepare", issues=value.get("issue_codes", []), projects=[value])
