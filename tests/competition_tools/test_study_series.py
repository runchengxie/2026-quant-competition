"""Portfolio curves bind the frozen date grid and verified summary metrics."""

import copy
from datetime import date, timedelta
import pytest
from competition_tools.evaluation.study_series import build_points


def test_missing_markets_have_no_fake_curves(tmp_path):
    from test_study_publication import blocked_study
    from competition_tools.evaluation.study_series import project_series

    value = project_series(blocked_study(tmp_path))
    assert value["series"] == []
    assert len(value["unavailable"]) == 3


@pytest.mark.parametrize(
    "mutation",
    [
        "private",
        "dict",
        "nan",
        "job",
        "plan",
        "fee",
        "missing",
        "duplicate",
        "anchor",
        "metric",
    ],
)
def test_public_curve_contract_rejects_tampering(mutation):
    import json
    from pathlib import Path
    from competition_tools.evaluation.study_series import validate_public_series

    root = Path(__file__).resolve().parents[2] / "site/src/data"
    value = json.loads((root / "real-data-series.v1.json").read_text(encoding="utf-8"))
    study = json.loads((root / "real-data-study.v1.json").read_text(encoding="utf-8"))
    curve = value["series"][0]
    if mutation == "private":
        curve["points"][0]["private_path"] = "C:/private"
    elif mutation == "dict":
        curve["points"] = {"date": {"note": "PRIVATE_SENTINEL"}}
    elif mutation == "nan":
        curve["points"][1]["net_nav"] = float("nan")
    elif mutation == "job":
        curve["job_id"] = "f" * 64
    elif mutation == "plan":
        value["plan_sha256"] = "f" * 64
    elif mutation == "fee":
        curve["cost_bps"] = True
    elif mutation == "missing":
        value["series"].pop()
    elif mutation == "duplicate":
        value["series"].append(copy.deepcopy(curve))
    elif mutation == "anchor":
        curve["points"][0]["net_nav"] = 0.99
    else:
        curve["points"][-1]["gross_nav"] += 0.1
    with pytest.raises(ValueError, match="INVALID_PUBLIC_STUDY_SERIES"):
        validate_public_series(value, study)


def curve_fixture():
    dates = [(date(2023, 1, 1) + timedelta(days=i)).isoformat() for i in range(315)]
    job = {"job_id": "a" * 64, "dates": dates, "fold": {"scoring_periods": 63}}
    result = {"metrics": {"net_return": 0.1, "gross_return": 0.2, "max_drawdown": 0.01}}
    periods = {
        "schema": "competition.daily_study_periods.v1",
        "job_id": job["job_id"],
        "net": [
            {
                "date": d,
                "equity": 0.99 if i == 0 else 1.1,
                "positions": {"PRIVATE_SENTINEL": "C:/private"},
            }
            for i, d in enumerate(dates[252:])
        ],
        "gross": [
            {"date": d, "equity": 1.0 if i == 0 else 1.2}
            for i, d in enumerate(dates[252:])
        ],
    }
    return job, result, periods


def test_curve_anchor_fee_and_private_fields():
    job, result, periods = curve_fixture()
    before = copy.deepcopy(periods)
    points = build_points(job, result, periods)
    assert points[0] == {
        "date": job["dates"][251],
        "net_nav": 1.0,
        "gross_nav": 1.0,
        "drawdown": 0.0,
    }
    assert len(points) == 64
    assert points[1]["net_nav"] == 0.99
    assert points[1]["drawdown"] == pytest.approx(0.01)
    assert points[-1]["net_nav"] == 1.1
    assert all(set(p) == {"date", "net_nav", "gross_nav", "drawdown"} for p in points)
    assert periods == before


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "date",
        "duplicate",
        "nan",
        "infinity",
        "bool",
        "negative",
        "job",
        "summary",
        "drawdown",
    ],
)
def test_invalid_period_evidence_is_rejected(mutation):
    job, result, periods = curve_fixture()
    if mutation == "missing":
        periods["net"].pop()
    elif mutation == "date":
        periods["net"][0]["date"] = "2020-01-01"
    elif mutation == "duplicate":
        periods["net"][1]["date"] = periods["net"][0]["date"]
    elif mutation in {"nan", "infinity", "bool", "negative"}:
        periods["net"][0]["equity"] = {
            "nan": float("nan"),
            "infinity": float("inf"),
            "bool": True,
            "negative": -1,
        }[mutation]
    elif mutation == "job":
        periods["job_id"] = "b" * 64
    elif mutation == "summary":
        result["metrics"]["net_return"] = 0.5
    else:
        result["metrics"]["max_drawdown"] = 0.5
    with pytest.raises(ValueError, match="INVALID_STUDY_SERIES"):
        build_points(job, result, periods)
