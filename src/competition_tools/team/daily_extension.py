"""Manual daily extension commands; preparation and inspection are offline."""

import json
from datetime import datetime, timezone

from ..datasets.binance_daily_acquisition import acquire_daily_extension, inspect_daily_extension
from ..datasets.binance_daily_spec import freeze_daily_extension
from ..datasets.binance_daily_transport import DailyTransport
from ..datasets.daily_storage import safe_path
from .processes import envelope


def execute(operation, config, *, spec=None, base_manifest=None, plan=None, manifest=None, output=None):
    if operation == "prepare" and spec and base_manifest and output:
        value = freeze_daily_extension(json.loads(safe_path(spec).read_text(encoding="utf-8-sig")), base_manifest, output, now=datetime.now(timezone.utc))
    elif operation == "inspect" and manifest:
        value = inspect_daily_extension(manifest)
    elif operation == "acquire" and plan and output:
        value = acquire_daily_extension(config, plan, output, transport=DailyTransport())
    else:
        raise ValueError("DAILY_EXTENSION_ARGUMENTS_REQUIRED")
    return envelope("daily-extension", issues=["DAILY_EXTENSION_BLOCKED"] if value.get("status") == "blocked" else [], projects=[value])
