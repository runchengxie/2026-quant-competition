"""Public cells preserve each requested fee, delay and unavailable result."""

import copy
import json
from pathlib import Path
from datetime import date, timedelta

import pytest
from jsonschema import Draft202012Validator, ValidationError

from competition_tools.evaluation.comparison_publication import (
    validate_cells,
    validate_public_comparison,
)


def cells():
    return [
        dict(
            window="2026-07-27",
            end="2026-08-21",
            arm=arm,
            fee_bps=fee,
            delay=delay,
            status="blocked",
            requested_dates=20,
            valid_dates=0,
            metrics=None,
            reasons=["MISSING_SELECTED_OUTCOME"],
        )
        for arm in ("equal_weight", "reversal", "ridge", "elastic_net")
        for fee in (0, 20, 40)
        for delay in (0, 1)
    ]


def test_fixed_grid_retains_unavailable_cells_without_zero_metrics():
    rows = cells()
    assert validate_cells("equity", rows, {"2026-07-27": "2026-08-21"}) == rows
    assert len(rows) == 24 and all(row["metrics"] is None for row in rows)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "boolean_fee",
        "fake_zero",
        "coverage",
        "private_path",
        "blocked_full",
    ],
)
def test_invalid_or_private_public_cells_fail(mutation):
    rows = cells()
    if mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows[-1] = copy.deepcopy(rows[0])
    elif mutation == "boolean_fee":
        rows[0]["fee_bps"] = False
    elif mutation == "fake_zero":
        rows[0]["metrics"] = {"net_return": 0}
    elif mutation == "coverage":
        rows[0]["valid_dates"] = 21
    elif mutation == "private_path":
        rows[0]["path"] = "C:/private/input.json"
    elif mutation == "blocked_full":
        rows[0]["valid_dates"] = 20
    with pytest.raises(ValueError):
        validate_cells("equity", rows, {"2026-07-27": "2026-08-21"})


def test_unreviewed_public_artifact_is_never_accepted():
    with pytest.raises(ValueError):
        validate_public_comparison(
            {"schema": "competition.strategy_comparison_public.v1"}
        )


def test_published_comparison_schema_matches_the_reviewed_aggregate():
    root = Path(__file__).resolve().parents[2]
    value = json.loads(
        (root / "site/src/data/strategy-comparison.v1.json").read_text(encoding="utf-8")
    )
    schema = json.loads(
        (root / "schemas/research/strategy-comparison-public.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(
        schema, format_checker=Draft202012Validator.FORMAT_CHECKER
    )
    validator.validate(value)
    assert validate_public_comparison(value) == value
    for changed in ("currency", "fee", "path", "missing_reason"):
        broken = copy.deepcopy(value)
        if changed == "currency":
            broken["crypto"]["currency"] = "USD"
        elif changed == "fee":
            broken["equity"]["accounts"][0]["fee_bps"] = False
        elif changed == "path":
            broken["scientific"]["path"] = "C:/private/source"
        else:
            next(
                row
                for row in broken["equity"]["accounts"]
                if row["status"] == "blocked"
            )["reasons"] = []
        with pytest.raises(ValidationError):
            validator.validate(broken)


def test_noncanonical_calendar_stops_before_export_io(tmp_path):
    from competition_tools.evaluation.comparison_evidence import verify_equity_export

    report = dict(
        schema="equity.strategy_comparison.v1",
        status="completed",
        retrospective=True,
        pnl_available=False,
        formal_common_stock_ready=False,
        calendar=[f"/outside/{i:03d}" for i in range(187)],
    )
    (tmp_path / "report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError):
        verify_equity_export(tmp_path)


def test_window_identity_cannot_become_an_absolute_artifact_path(tmp_path):
    from competition_tools.evaluation.comparison_evidence import verify_crypto_export

    windows, rows = [], []
    for i in range(12):
        days = [
            (date(2020, 1, 1) + timedelta(days=i * 90 + j)).isoformat()
            for j in range(342)
        ]
        identity = str(tmp_path / "outside") if i == 0 else days[252]
        windows.append(
            dict(
                window_id=identity,
                bars=dict(dates=days, close={str(p): [100.0] * 342 for p in range(8)}),
            )
        )
        for arm in [
            "buy_hold_equal_weight",
            "fixed60_weekly",
            "trend_weekly",
            "matched_weekly",
        ]:
            for fee in [0, 35, 50]:
                for delay in [0, 1]:
                    rows.append(
                        dict(
                            window=identity,
                            arm=arm,
                            fee_bps=fee,
                            delay=delay,
                            path=f"{identity}-{arm}-{fee}-{delay}.json",
                        )
                    )
    folder = tmp_path / "export"
    folder.mkdir()
    (folder / "report.json").write_text(
        json.dumps(
            dict(
                schema="crypto.strategy_comparison.v1",
                status="completed",
                retrospective=True,
                quote_currency="USDT",
                accounts=rows,
            )
        )
    )
    with pytest.raises(ValueError):
        verify_crypto_export(
            folder, dict(schema="crypto.weekly_input.v1", windows=windows)
        )
