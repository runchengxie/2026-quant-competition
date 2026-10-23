"""The bounded diagnostic grid is not a tunable parameter search."""

import pytest


def parent_jobs():
    jobs = []
    for i in range(11):
        for fee in (20, 40):
            jobs.append(dict(market="US", arm_id="ew_monthly", fee_bps=fee, fold=dict(start=f"window-{i}")))
    for i in range(12):
        for arm in ("trend200_vol40_strict", "ew_trend_gross_matched"):
            jobs.append(dict(market="crypto", arm_id=arm, fee_bps=25, fold=dict(start=f"window-{i}")))
    return jobs


def test_exact_114_jobs_and_unchanged_original_cost_catalog():
    from competition_tools.evaluation.robustness.catalog import diagnostic_grid
    from competition_tools.evaluation.controls.catalog import COSTS

    grid = diagnostic_grid(parent_jobs())
    assert len(grid) == 114
    assert sum(j["input_job"]["market"] == "US" for j in grid) == 66
    assert sum(j["input_job"]["market"] == "crypto" for j in grid) == 48
    assert {j["fee_bps"] for j in grid if j["input_job"]["market"] == "crypto"} == {35, 50}
    assert COSTS == {"US": [20, 40], "crypto": [0, 10, 25]}


def test_missing_or_duplicate_parent_comparisons_block():
    from competition_tools.evaluation.robustness.catalog import diagnostic_grid

    for jobs in (parent_jobs()[:-1], parent_jobs() + [parent_jobs()[0]]):
        with pytest.raises(ValueError):
            diagnostic_grid(jobs)


def test_invalid_spec_rejects_tuning_or_new_costs(tmp_path):
    from competition_tools.evaluation.robustness.contracts import validate_spec

    spec = dict(schema="competition.strategy_robustness_spec.v1", parent_plan=str(tmp_path / "plan.json"), parent_results=str(tmp_path / "results.json"), expected_parent_plan_sha256="a"*64, expected_parent_results_sha256="b"*64, role="retrospective_diagnostic", accepted_research=False)
    assert validate_spec(spec) == spec
    with pytest.raises(ValueError):
        validate_spec(spec | {"costs": [0, 1, 2]})


def test_market_reservation_cannot_be_repeated(tmp_path):
    from competition_tools.evaluation.robustness.runner import reserve_market

    parent = tmp_path / "historical/plan.json"
    parent.parent.mkdir()
    parent.write_text(str(tmp_path))
    from competition_tools.datasets.storage import digest
    first = reserve_market(parent, digest(parent), "US")
    assert first.is_dir()
    with pytest.raises(FileExistsError):
        reserve_market(parent, digest(parent), "US")


def test_arbitrary_parent_hash_cannot_grant_new_budget(tmp_path):
    from competition_tools.evaluation.robustness.runner import reserve_market

    parent=tmp_path / "parent.json"
    parent.write_text("{}")
    with pytest.raises(ValueError,match="PARENT"):
        reserve_market(parent,"f"*64,"US")


def test_changed_parent_hash_blocks_before_source_snapshot(tmp_path):
    from competition_tools.evaluation.robustness.plan import freeze_robustness

    parent = tmp_path / "parent.json"
    parent.write_text("{}")
    spec = dict(schema="competition.strategy_robustness_spec.v1",parent_plan=str(parent),parent_results=str(parent),expected_parent_plan_sha256="a"*64,expected_parent_results_sha256="b"*64,role="retrospective_diagnostic",accepted_research=False)
    with pytest.raises(ValueError, match="PARENT"):
        freeze_robustness(spec,tmp_path / "output",code_identity={})
    assert not (tmp_path / "output").exists()


def test_robustness_cli_help_is_configuration_free(capsys):
    from competition_tools.team.__main__ import main

    with pytest.raises(SystemExit) as exit:
        main(["robustness","--help"])
    assert exit.value.code == 0
    assert "--spec" in capsys.readouterr().out
