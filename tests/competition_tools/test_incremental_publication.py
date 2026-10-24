from copy import deepcopy
import json
from pathlib import Path

import pytest

SOURCE = (
    Path(__file__).resolve().parents[2] / "site/src/data/incremental-research.v1.json"
)


def test_reviewed_incremental_aggregate_is_valid():
    from competition_tools.evaluation.incremental_publication import (
        validate_public_incremental,
    )

    data = json.loads(SOURCE.read_text())
    assert validate_public_incremental(data) == data


@pytest.mark.parametrize(
    "mutation",
    ["private", "nonfinite", "boolean", "rows", "date", "changed_ic", "crypto_count"],
)
def test_incremental_publication_rejects_changed_or_private_facts(mutation):
    from competition_tools.evaluation.incremental_publication import (
        validate_public_incremental,
    )

    data = deepcopy(json.loads(SOURCE.read_text()))
    if mutation == "private":
        data["equity"]["account"] = "private"
    elif mutation == "nonfinite":
        data["crypto"]["jobs"][0]["metrics"]["net_return"] = float("nan")
    elif mutation == "boolean":
        data["equity"]["fit_attempts"] = True
    elif mutation == "rows":
        data["equity"]["folds"][0]["test_candidate_count"] = 1
    elif mutation == "date":
        data["equity"]["folds"][0]["models"][0]["metrics"]["daily"][0]["date"] = (
            "2026-07-25"
        )
    elif mutation == "changed_ic":
        data["equity"]["folds"][0]["models"][3]["metrics"]["mean_daily_ic"] += 0.01
    else:
        data["crypto"]["net_simulations"] = 121
    with pytest.raises((ValueError, TypeError)):
        validate_public_incremental(data)
