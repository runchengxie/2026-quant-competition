import copy
import json
from pathlib import Path
from datetime import date, timedelta
from itertools import product

import pytest

from competition_tools.evaluation.low_turnover_publication import (
    validate_candidate,
    parse_reviewed,
)


def candidate():
    stock_windows = ["2026-01-02", "2026-03-02"]
    variants = [("equal_weight", 0)] + list(
        product(("reversal", "ridge", "elastic_net"), (0, 20))
    )
    accounts = [
        dict(
            horizon=h,
            window=w,
            end=(date.fromisoformat(w) + timedelta(days=55)).isoformat(),
            arm=a,
            buffer=b,
            fee_bps=f,
            delay=d,
            status="blocked",
            reason="MODEL_UNAVAILABLE",
            blocked_date=(date.fromisoformat(w) + timedelta(days=1)).isoformat(),
            requested_dates=41,
            valid_dates=0,
            metrics=None,
        )
        for h, w, (a, b), f, d in product(
            (5, 20), stock_windows, variants, (0, 20, 40), (0, 1)
        )
    ]
    models = [
        dict(
            horizon=h,
            window=w,
            end=(date.fromisoformat(w) + timedelta(days=55)).isoformat(),
            model=m,
            status="unavailable",
            params=None,
            prediction_rows=0,
            training_rows=5000,
            inner_training_rows=3000,
            metrics=None,
        )
        for h, w, m in product((5, 20), stock_windows, ("ridge", "elastic_net"))
    ]
    old_windows = ["2026-01-01", "2026-02-01", "2026-03-01"]
    costs = [
        dict(
            window=w,
            arm=a,
            delay=d,
            status="blocked",
            valid_dates=0,
            requested_dates=20,
            gross_return=None,
            break_even_one_way_bps=None,
            mean_daily_turnover=None,
        )
        for w, a, d in product(
            old_windows, ("equal_weight", "reversal", "ridge", "elastic_net"), (0, 1)
        )
    ]
    crypto = [
        dict(
            window=(start := date(2023, 1, 1) + timedelta(days=i * 100)).isoformat(),
            end=(start + timedelta(days=89)).isoformat(),
            arm=a,
            fee_bps=f,
            delay=d,
            net_return=0.0,
            components=dict(market=0.0, exposure=0.0, selection=0.0, cost=0.0),
            dates=90,
            mean_post_trade_exposure=0.0,
            down_market_dates=0,
            down_market_strategy_pnl=0.0,
            down_market_full_reference_pnl=0.0,
        )
        for i, a, f, d in product(
            range(12),
            (
                "buy_hold_equal_weight",
                "fixed60_weekly",
                "trend_weekly",
                "matched_weekly",
            ),
            (0, 35, 50),
            (0, 1),
        )
    ]
    security = dict(
        schema="competition.security_evidence_audit.v1",
        candidate_days=1,
        identity_segments=1,
        unresolved_identity_segments=1,
        unresolved_candidate_days=1,
        unmatched_interval_days=0,
        missing_master_days=0,
        source_classifications={"unverified_security_type": 1},
        source_seed_events=0,
        source_split_seeds=0,
        seed_split_boundary_matches=0,
        large_raw_boundary_jumps=0,
        independently_verified_type_days=0,
        corporate_action_coverage="incomplete",
        availability_verified=False,
        formal_performance_ready=False,
        prices_modified=False,
        primary_announcements_reviewed=0,
    )
    return dict(
        schema="competition.low_turnover_public.v1",
        retrospective=True,
        formal_performance_ready=False,
        scientific=dict(
            commit="a" * 40,
            plan_sha256="a" * 64,
            result_sha256="b" * 64,
            daily_input_sha256="c" * 64,
            parent_comparison_sha256="e808a27d1a7bfb6a40bc7f33541849dea72047ef0fdbb692dfab1dd98abe62ac",
        ),
        equity=dict(currency="USD", fit_attempts=48, models=models, accounts=accounts),
        cost_diagnostics=dict(requested=24, completed=0, accounts=costs),
        crypto=dict(currency="USDT", accounts=crypto),
        security=security,
        observation=dict(
            status="awaiting_new_data",
            registry_frozen=False,
            protocol_id=None,
            frozen_at="2026-10-25T00:00:00+00:00",
            crypto_warmup_end="2026-09-30",
            us_warmup_end="2026-09-30",
            accepted_observations=0,
            first_eligible_observation_at=None,
            download=dict(status="not_attempted", attempts=0, transferred_bytes=0),
            issue_codes=["STALE_WARMUP"],
        ),
    )


def test_complete_bounded_candidate_is_valid_but_not_automatically_reviewed():
    value = candidate()
    assert validate_candidate(value) == value
    with pytest.raises(ValueError):
        parse_reviewed(json.dumps(value))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda v: v.update(private_path="C:/private"),
        lambda v: v["equity"]["accounts"].pop(),
        lambda v: v["equity"]["accounts"][0].update(metrics={"net_return": 0}),
        lambda v: v["crypto"]["accounts"][0]["components"].update(market=0.1),
        lambda v: v["equity"].update(currency="USDT"),
        lambda v: v["observation"].update(accepted_observations=1),
        lambda v: v["security"].update(formal_performance_ready=True),
        lambda v: v["equity"]["accounts"][0].update(window="../../private"),
    ],
)
def test_unknown_private_fields_missing_cells_and_promoted_evidence_are_rejected(
    mutation,
):
    value = copy.deepcopy(candidate())
    mutation(value)
    with pytest.raises(ValueError):
        validate_candidate(value)


def test_duplicate_json_fields_are_rejected_even_with_matching_reviewed_hash(
    monkeypatch,
):
    from competition_tools.evaluation.study_identity import canonical_hash
    import competition_tools.evaluation.low_turnover_publication as publication

    value = candidate()
    monkeypatch.setattr(publication, "REVIEWED_SHA256", canonical_hash(value))
    assert parse_reviewed(json.dumps(value)) == value
    with pytest.raises(ValueError):
        parse_reviewed('{"retrospective":false,' + json.dumps(value)[1:])


def test_public_json_schema_accepts_null_and_completed_shapes_and_is_closed():
    import jsonschema

    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "schemas/research/low-turnover-public.v1.schema.json"
        ).read_text()
    )
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )
    value = candidate()
    validator.validate(value)
    row = value["equity"]["accounts"][0]
    row.update(
        status="completed",
        reason=None,
        blocked_date=None,
        valid_dates=41,
        metrics=dict(
            net_return=0.0,
            gross_return=0.0,
            cost_drag=0.0,
            total_costs=0.0,
            turnover=2.0,
            max_drawdown=0.0,
        ),
    )
    validator.validate(value)
    row["metrics"]["private_position"] = "A"
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(value)
