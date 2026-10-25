"""Only reviewed closed aggregates may describe new research progress."""

import copy
import json
from pathlib import Path

import pytest

from competition_tools.evaluation.followup_publication import (
    validate_candidate,
    parse_reviewed,
    summary,
)


def candidate():
    return json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "site/src/data/evidence-followup.v1.json"
        ).read_text(encoding="utf-8")
    )


def test_actual_candidate_has_complete_grid_and_honest_observation_status():
    value = candidate()
    assert validate_candidate(value) is value
    rendered = summary(value)
    assert rendered["completed"] == 156 and rendered["blocked"] == 12
    assert rendered["accepted_stocks"] == 0
    assert rendered["accepted_observations"] == 0
    assert parse_reviewed(json.dumps(value)) == value


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x.update(private_account="synthetic-forbidden"),
        lambda x: x["equity"]["accounts"].pop(),
        lambda x: x["equity"].update(currency="USDT"),
        lambda x: x["crypto"].update(return_wins=72),
        lambda x: x["security"].update(accepted=10),
        lambda x: x["observation"].update(accepted_observations=1),
        lambda x: x["observation"].update(new_bytes=float("nan")),
    ],
)
def test_private_or_promoted_or_changed_facts_are_rejected(change):
    value = copy.deepcopy(candidate())
    change(value)
    with pytest.raises(ValueError):
        validate_candidate(value)


def test_duplicate_json_keys_cannot_enter_reviewed_publication():
    value = json.dumps(candidate())
    with pytest.raises(ValueError):
        parse_reviewed(value[:-1] + ', "validation_sessions": 60}')
