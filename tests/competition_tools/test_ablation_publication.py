"""Public ablation facts exclude private locators and preserve evidence roles."""

import copy
import json
from pathlib import Path
import pytest
from competition_tools.evaluation.ablation_catalog import CATALOG_SHA256, variant_spec
from competition_tools.evaluation.ablation_publication import (
    validate_public_ablation,
    pair_public_rows,
)


def public_fixture():
    source = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "site/src/data/real-data-study.v1.json"
        ).read_text()
    )
    base = copy.deepcopy(
        next(
            r
            for r in source["results"]
            if r["market"] == "US" and r["strategy"] == "sma_cross"
        )
    )
    original = next(m for m in source["methods"] if m["method_id"] == base["method_id"])
    rows = []
    methods = []
    for variant, id_, net in [("baseline", "a", 0.01), ("weekly", "b", 0.04)]:
        r = copy.deepcopy(base)
        p = variant_spec("US", "sma_cross", variant)
        r.update(
            job_id=id_ * 64,
            net_return=net,
            gross_return=net + 0.01,
            cost_drag=0.01,
            **p,
        )
        r["method_id"] = "us.sma_cross." + variant + ".self_financing_daily.v1"
        method = {**original, **p, "method_id": r["method_id"]}
        if variant != "baseline":
            method["rebalance"] = variant
        rows.append(r)
        methods.append(method)
    pair_public_rows(rows)
    return {
        **source,
        "schema": "competition.public_ablation.v1",
        "catalog_sha256": CATALOG_SHA256,
        "origin": {
            **{
                k: "c" * 64
                for k in [
                    "probe_protocol_sha256",
                    "diagnostic_protocol_sha256",
                    "evidence_manifest_sha256",
                ]
            },
            "stage": "retrospective",
            "retrospective": True,
            "accepted_research": False,
        },
        "results": rows,
        "methods": methods,
    }


def test_missing_baseline_has_null_paired_changes():
    v = public_fixture()
    assert v["results"][1]["paired_net_change"] == pytest.approx(0.03)
    v["results"] = v["results"][1:]
    pair_public_rows(v["results"])
    assert v["results"][0]["paired_net_change"] is None
    validate_public_ablation(v)


def test_nested_private_sentinel_is_rejected():
    v = public_fixture()
    validate_public_ablation(v)
    v["results"][0]["variant_parameters"]["account_id"] = "PRIVATE_SENTINEL"
    with pytest.raises(ValueError):
        validate_public_ablation(v)


@pytest.mark.parametrize(
    "change", ["role", "paired", "catalog", "nonfinite", "duplicate", "method"]
)
def test_post_hoc_role_matches_catalog_and_plan(change):
    v = public_fixture()
    if change == "role":
        v["results"][1]["evidence_role"] = "forward_validated"
    elif change == "paired":
        v["results"][1]["paired_net_change"] = 10
    elif change == "catalog":
        v["catalog_sha256"] = "d" * 64
    elif change == "nonfinite":
        v["results"][1]["net_return"] = float("nan")
    elif change == "duplicate":
        v["results"][1]["job_id"] = v["results"][0]["job_id"]
    elif change == "method":
        v["methods"][1]["variant_parameters"]["secret"] = "PRIVATE_SENTINEL"
    with pytest.raises(ValueError):
        validate_public_ablation(v)


def test_public_schema_agrees_and_rejects_opposite_family():
    import jsonschema

    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "schemas/research/public-ablation.v1.schema.json"
        ).read_text()
    )
    v = public_fixture()
    jsonschema.validate(v, schema)
    v["schema"] = "competition.public_study.v1"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(v, schema)
    with pytest.raises(ValueError):
        validate_public_ablation(v)


def test_schema_rejects_relabeling_weekly_as_post_hoc():
    import jsonschema

    schema = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "schemas/research/public-ablation.v1.schema.json"
        ).read_text()
    )
    v = public_fixture()
    v["results"][1]["evidence_role"] = "post_hoc_diagnostic"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(v, schema)
    with pytest.raises(ValueError):
        validate_public_ablation(v)


def test_public_fee_rejects_boolean_zero():
    v = public_fixture()
    from competition_tools.evaluation.ablation_runner import methods_for

    for r in v["results"]:
        r.update(
            market="crypto",
            quote_currency="USDT",
            strategy="trend_200d",
            variant_id="baseline",
            variant_parameters={},
            cost_bps=False,
            benchmark="equal_weight",
            products=["BTCUSDT"],
            periods_per_year=365,
        )
        r["fold"]["scoring_periods"] = 90
        r["sessions"] = 90
        r["method_id"] = "crypto.trend_200d.baseline.self_financing_daily.v1"
    v["results"] = v["results"][:1]
    v["methods"] = [
        methods_for(
            {
                "market": "crypto",
                "strategy": "trend_200d",
                "variant_id": "baseline",
                "variant_parameters": {},
                "evidence_role": "retrospective_ablation",
                "fold": {"scoring_periods": 90},
            }
        )
    ]
    pair_public_rows(v["results"])
    with pytest.raises(ValueError):
        validate_public_ablation(v)
