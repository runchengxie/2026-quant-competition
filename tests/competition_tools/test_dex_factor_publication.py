import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from competition_tools.evaluation.dex_factor_publication import (
    build_public_dex_factors,
    validate_public_dex_factors,
)
from competition_tools.datasets.dex_acquisition import acquire_dex
from competition_tools.datasets.dex_spec import dataset_identity
from competition_tools.datasets.storage import digest, write_json
from competition_tools.team.factors import SIGNALS
from test_dex_acquisition import case

RESTRICTIONS = [
    "fixed_current_selection",
    "bar_close_proxy_unverified",
    "gross_descriptive_forward_returns",
    "not_portfolio_pnl",
    "no_cost_or_execution_model",
    "no_out_of_sample_or_significance_claim",
]


@pytest.fixture
def private_factor_case(tmp_path):
    spec, staging, transport, _ = case(tmp_path)
    root = Path(__file__).resolve().parents[2]
    package = root / "research/crypto-mm/src/crypto_mm"
    protocol = dict(
        schema="competition.dex_factor_protocol.v1",
        dataset=dataset_identity(spec),
        manifest_file=str(staging / "manifest.json"),
        source_commit="a" * 40,
        source_files=[
            dict(path=p.relative_to(package).as_posix(), sha256=digest(p))
            for p in sorted((package / "factors").glob("*.py"))
        ],
        signals=SIGNALS,
        horizons=[6, 24],
        sampling=["all_valid", "non_overlapping"],
        role="retrospective",
        parameter_search=False,
        minimum_overall=30,
        minimum_slice=20,
        slices=3,
        slice_hours=720,
        groups=3,
        minimum_underlyings=9,
        minimum_per_group=3,
        availability="bar_close_proxy_unverified",
    )
    write_json(Path(spec["protocol_file"]), protocol)
    spec["protocol_sha256"] = digest(Path(spec["protocol_file"]))
    acquire_dex(spec, staging, transport=transport)
    manifest = json.loads((staging / "manifest.json").read_text())
    temporal, cross = [], []
    for signal in SIGNALS:
        width = (
            25
            if signal == "momentum_24h"
            else 169
            if signal == "momentum_168h"
            else 192
        )
        for horizon in (6, 24):
            for sampling in ("all_valid", "non_overlapping"):
                times = [
                    i
                    for i in range(width, 2161 - horizon)
                    if sampling == "all_valid" or i % horizon == 0
                ]

                def metric(n, minimum=30):
                    return dict(
                        value=None,
                        n=n,
                        reason="CONSTANT_SIGNAL"
                        if n >= minimum
                        else "INSUFFICIENT_OBSERVATIONS",
                    )

                temporal.append(
                    dict(
                        asset_id="wrapped-sol",
                        signal_id=signal,
                        horizon=horizon,
                        sampling=sampling,
                        overall=metric(len(times)),
                        slices=[
                            dict(
                                index=i,
                                **metric(
                                    sum(i * 720 <= t < (i + 1) * 720 for t in times), 20
                                ),
                            )
                            for i in range(3)
                        ],
                    )
                )
                cross.append(
                    dict(
                        signal_id=signal,
                        horizon=horizon,
                        sampling=sampling,
                        candidate_timestamps=len(times),
                        valid_timestamps=0,
                        mean_rank_ic=None,
                        group_mean_forward_returns=None,
                        top_minus_bottom=None,
                        reason="INSUFFICIENT_UNDERLYINGS",
                        excluded_reasons={"INSUFFICIENT_UNDERLYINGS": len(times)},
                    )
                )
    result = dict(
        schema="competition.dex_factor_result.v1",
        status="completed",
        dataset=protocol["dataset"],
        source_commit=protocol["source_commit"],
        protocol_sha256=manifest["protocol_sha256"],
        manifest_sha256=digest(staging / "manifest.json"),
        input_hashes={r["path"]: r["sha256"] for r in manifest["files"]},
        source_files=protocol["source_files"],
        role="retrospective",
        coverage=[
            dict(
                asset_id="wrapped-sol", observed_intervals=2160, expected_intervals=2160
            )
        ],
        time_series=temporal,
        cross_sectional=cross,
        restrictions=RESTRICTIONS,
    )
    for name, value in [
        ("dex-factor-protocol.v1", protocol),
        ("dex-factor-result.v1", result),
        ("dex-dataset-manifest.v1", manifest),
    ]:
        Draft202012Validator(
            json.loads(
                (root / "schemas/research" / (name + ".schema.json")).read_text()
            )
        ).validate(value)
    return protocol, manifest, result


def permission(protocol=None):
    value = dict(
        status="verified",
        scope="derived_statistics",
        source_url="https://dexpaprika.com/api/terms",
        source_sha256="b" * 64,
        checked_at="2026-10-22T00:00:00Z",
        conclusion="aggregate_publication_permitted",
    )
    if protocol is not None:
        source = (
            Path(protocol["manifest_file"]).parent.parent
            / "synthetic-permission-source.txt"
        )
        clause = "Publication of derived research statistics is permitted."
        source.write_text("Synthetic license fixture only. " + clause)
        value.update(
            source_file=str(source),
            source_sha256=digest(source),
            supporting_clause=clause,
        )
    return value


def test_unresolved_rights_cannot_leak_metrics(private_factor_case):
    value = build_public_dex_factors(*private_factor_case, {"status": "unresolved"})
    assert value["status"] == "readiness_only"
    assert "metrics" not in value and "coverage" not in value
    assert "PUBLICATION_PERMISSION_UNVERIFIED" in value["blockers"]
    validate_public_dex_factors(value)


def test_permission_boolean_cannot_authorize_publication(private_factor_case):
    value = build_public_dex_factors(*private_factor_case, {"approved": True})
    assert value["status"] == "readiness_only"


def test_permission_metadata_without_retained_source_cannot_authorize(
    private_factor_case,
):
    value = build_public_dex_factors(*private_factor_case, permission())
    assert value["status"] == "readiness_only"


def test_blocked_acquisition_can_publish_readiness_without_invented_result(
    private_factor_case,
):
    protocol, manifest, _ = private_factor_case
    path = Path(protocol["manifest_file"])
    receipt_path = path.parent / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt.update(status="blocked", issues=["HTTP_403"])
    write_json(receipt_path, receipt)
    manifest.update(status="blocked", issues=["HTTP_403"])
    for record in manifest["files"]:
        if record["path"] == "receipt.json":
            record.update(
                sha256=digest(receipt_path), bytes=receipt_path.stat().st_size
            )
    write_json(path, manifest)
    path.parent.rename(path.parent.with_name(path.parent.name + ".partial"))
    value = build_public_dex_factors(protocol, manifest, None, {"status": "unresolved"})
    assert value["status"] == "readiness_only"
    assert "DEX_ACQUISITION_BLOCKED" in value["blockers"]
    assert "metrics" not in value


def test_permitted_synthetic_projection_excludes_private_fields(private_factor_case):
    value = build_public_dex_factors(
        *private_factor_case, permission(private_factor_case[0])
    )
    assert value["status"] == "measured"
    assert len(value["metrics"]["time_series"]) == 16
    assert "credential_file" not in json.dumps(value)
    assert "manifest_file" not in json.dumps(value)
    validate_public_dex_factors(value)
    root = Path(__file__).resolve().parents[2]
    Draft202012Validator(
        json.loads(
            (root / "schemas/research/public-dex-factors.v1.schema.json").read_text()
        )
    ).validate(value)


@pytest.mark.parametrize(
    "mutation", ["unknown", "bool", "nan", "counts", "source", "hash", "coverage"]
)
def test_invalid_private_results_rejected(private_factor_case, mutation):
    protocol, manifest, result = copy.deepcopy(private_factor_case)
    if mutation == "unknown":
        result["time_series"][0]["private_path"] = "C:/private"
    if mutation == "bool":
        result["time_series"][0]["overall"]["value"] = True
    if mutation == "nan":
        result["time_series"][0]["overall"]["value"] = float("nan")
    if mutation == "counts":
        result["time_series"][0]["overall"]["n"] += 1
    if mutation == "source":
        result["source_commit"] = "c" * 40
    if mutation == "hash":
        result["manifest_sha256"] = "0" * 64
    if mutation == "coverage":
        result["coverage"][0]["observed_intervals"] -= 1
    with pytest.raises(ValueError):
        build_public_dex_factors(protocol, manifest, result, permission(protocol))


def test_unexpected_public_keys_and_paths_rejected(private_factor_case):
    value = build_public_dex_factors(*private_factor_case, {"status": "unresolved"})
    with pytest.raises(ValueError):
        validate_public_dex_factors(value | {"path": "C:/private"})
    value["asset_ids"][0] = "C:/private"
    with pytest.raises(ValueError):
        validate_public_dex_factors(value)


def test_mutation_during_projection_invalidates_publication(
    private_factor_case, monkeypatch
):
    from competition_tools.evaluation import dex_factor_publication as publication

    original = publication.verify_counts
    protocol, manifest, result = private_factor_case

    def mutate(*args):
        original(*args)
        (Path(protocol["manifest_file"]).parent / "raw/networks.json").write_text("[]")

    monkeypatch.setattr(publication, "verify_counts", mutate)
    with pytest.raises(ValueError, match="DATASET_HASH_MISMATCH"):
        publication.build_public_dex_factors(
            protocol, manifest, result, permission(protocol)
        )
