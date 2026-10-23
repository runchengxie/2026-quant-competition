"""Manual observation commands never acquire data or activate a scheduler."""

from datetime import datetime, timezone

from ..datasets.daily_storage import safe_path
from ..evaluation.controls.contracts import read_json
from ..evaluation.observation_registry import (
    append_observation,
    freeze_observation,
    inspect_observation,
)
from .processes import envelope


def execute(operation, config, registry_root, *, spec=None, manifest=None):
    if operation == "freeze":
        if spec is None or manifest is not None:
            raise ValueError("OBSERVATION_FREEZE_SPEC_REQUIRED")
        value = freeze_observation(
            read_json(safe_path(spec)), registry_root, now=datetime.now(timezone.utc)
        )
    elif operation == "append":
        if manifest is None or spec is not None:
            raise ValueError("OBSERVATION_IMPORT_MANIFEST_REQUIRED")
        value = append_observation(
            registry_root, manifest, config=config, now=datetime.now(timezone.utc)
        )
    elif operation == "status":
        if spec is not None or manifest is not None:
            raise ValueError("OBSERVATION_STATUS_TAKES_NO_INPUT")
        value = inspect_observation(registry_root)
    else:
        raise ValueError("INVALID_OBSERVATION_OPERATION")
    return envelope("observe", projects=[value])
