import json

import pytest

from competition_tools.evaluation.low_turnover_evidence import verify_holding_export


@pytest.mark.parametrize(
    "calendar", [["../../outside"], ["2026-01-01", "2026-01-01"], ["2026-02-30"]]
)
def test_export_rejects_invalid_calendar_before_opening_named_artifacts(
    tmp_path, calendar
):
    report = dict(
        schema="equity.low_turnover_ml.v1",
        status="completed",
        retrospective=True,
        formal_performance_ready=False,
        currency="USD",
        calendar=calendar,
        accounts=[],
        models=[],
        fit_attempts=0,
    )
    (tmp_path / "report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError):
        verify_holding_export(tmp_path)


def test_export_rejects_missing_requested_accounts_without_reading_predictions(
    tmp_path,
):
    from datetime import date, timedelta

    report = dict(
        schema="equity.low_turnover_ml.v1",
        status="completed",
        retrospective=True,
        formal_performance_ready=False,
        currency="USD",
        calendar=[
            (date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(230)
        ],
        accounts=[],
        models=[],
        fit_attempts=0,
    )
    (tmp_path / "report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="HOLDING_GRID"):
        verify_holding_export(tmp_path)
