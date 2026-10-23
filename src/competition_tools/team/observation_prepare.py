"""Offline preparation, with no broker-session import or service activation."""

from datetime import datetime, timezone

from ..evaluation.observation_preparation import (
    prepare_observation,
    prepare_us_refresh,
    freeze_prepared_market,
)
from .processes import envelope


def execute(
    operation, config, manifest, output, *, parent_registry=None, preparation=None
):
    if operation == "us-refresh" and manifest:
        value = prepare_us_refresh(config, manifest, datetime.now(timezone.utc), output)
    elif operation == "market" and parent_registry and manifest:
        value = prepare_observation(
            config, manifest, output, parent_registry=parent_registry
        )
    elif operation == "freeze-market" and parent_registry and preparation:
        value = freeze_prepared_market(
            config, preparation, parent_registry, output, now=datetime.now(timezone.utc)
        )
    else:
        raise ValueError("PREPARATION_ARGUMENTS_REQUIRED")
    return envelope(
        "observation-prepare", issues=value.get("issue_codes", []), projects=[value]
    )
