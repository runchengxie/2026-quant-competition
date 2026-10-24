import copy
import json
from pathlib import Path

import pytest

from competition_tools.evaluation.predictive_publication import (
    validate_public_predictive,
)


def fixture():
    return json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "site/src/data/equity-predictive.v1.json"
        ).read_text()
    )


def test_reviewed_predictive_projection_reconciles_each_daily_mean():
    assert (
        validate_public_predictive(fixture())["scope"]
        == "retrospective_source_candidate_prediction"
    )


@pytest.mark.parametrize(
    "mutation", ["bool", "nan", "extra", "mean", "pnl", "coverage"]
)
def test_predictive_projection_rejects_changed_facts_and_private_fields(mutation):
    data = copy.deepcopy(fixture())
    if mutation == "bool":
        data["fit_attempts"] = True
    elif mutation == "nan":
        data["folds"][0]["models"][0]["metrics"]["mean_daily_ic"] = float("nan")
    elif mutation == "extra":
        data["private_path"] = "not-public"
    elif mutation == "mean":
        data["folds"][0]["models"][0]["metrics"]["mean_daily_ic"] += 0.1
    elif mutation == "pnl":
        data["pnl_available"] = True
    else:
        data["folds"][0]["models"][0]["metrics"]["valid_ic_dates"] = 19
    with pytest.raises(ValueError):
        validate_public_predictive(data)
