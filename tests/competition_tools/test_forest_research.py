"""Closed forest protocol and complete predetermined paired family."""

from itertools import product
import os
import subprocess
import pytest

from competition_tools.evaluation.forest_study import rules
from competition_tools.evaluation.forest_study_validation import paired


def test_forest_budget_does_not_expand_old_tree_rules():
    from competition_tools.evaluation.tree_study import rules as old_rules

    new = rules()
    assert new["maximum_attempts_total"] == 24
    assert new["maximum_attempts_per_horizon"] == 12
    assert old_rules()["maximum_attempts_per_horizon"] == 6
    assert new["reused_requested_accounts"] == 264
    assert new["new_requested_accounts"] == 96
    assert new["depths"] == [3, 5]
    assert len(new["estimator_parameters"]) == 2
    assert new["scientific_requirements"] == "all_six_remain_blocked"


def test_real_root_launch_rejects_nonretained_input_before_reservation_read(
    monkeypatch,
):
    from competition_tools.evaluation import forest_study

    monkeypatch.setattr(
        forest_study, "verify_binding", lambda *args: {"input_sha256": "0" * 64}
    )
    with pytest.raises(ValueError, match="FOREST_RETAINED_INPUT_REQUIRED"):
        forest_study.run("not-read", "not-read", "must-never-launch")


def test_complete_fixed_comparisons_preserve_blocked_cells_and_eq_buffer():
    windows = ["2026-05-28", "2026-07-27"]
    accounts = [
        dict(
            horizon=h,
            window=w,
            arm=arm,
            buffer=b,
            fee_bps=fee,
            delay=delay,
            metrics=dict(net_return=b / 100),
            status="completed",
        )
        for h, w, arm, b, fee, delay in product(
            (5, 20),
            windows,
            (
                "random_forest",
                "extra_trees",
                "equal_weight",
                "reversal",
                "momentum20",
                "ridge",
                "elastic_net",
                "shallow_tree",
            ),
            (0, 20),
            (0, 20, 40),
            (0, 1),
        )
    ]
    accounts[0].update(status="blocked", metrics=None)
    result = paired(accounts, windows)
    assert len(result) == 576
    assert sum(r["reason"] == "unavailable_account" for r in result) == 6
    assert all(
        r["difference"] == 0.2
        for r in result
        if r["reference"] == "equal_weight" and r["buffer"] == 20
    )


def test_extra_retained_symlink_rejected_before_hashing(tmp_path):
    from competition_tools.evaluation.forest_study import _retained_records

    output = tmp_path / "retained"
    output.mkdir()
    target = tmp_path / "unbound.txt"
    target.write_text("not retained evidence")
    try:
        (output / "extra.txt").symlink_to(target)
    except OSError:
        pytest.skip("Platform cannot create file symlinks")
    with pytest.raises(ValueError, match="REPARSE"):
        _retained_records(output)


def test_extra_retained_dangling_symlink_rejected(tmp_path):
    from competition_tools.evaluation.forest_study import _retained_records

    output = tmp_path / "retained"
    output.mkdir()
    try:
        (output / "extra.txt").symlink_to(tmp_path / "missing")
    except OSError:
        pytest.skip("Platform cannot create file symlinks")
    with pytest.raises(ValueError, match="REPARSE"):
        _retained_records(output)


def test_source_alias_rejected_before_resolve_or_reservation(tmp_path):
    from competition_tools.evaluation.forest_study import prepare

    source = tmp_path / "source"
    source.mkdir()
    alias = tmp_path / "source-alias"
    try:
        alias.symlink_to(source, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            pytest.skip("Platform cannot create directory symlinks")
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(source)],
            check=True,
            capture_output=True,
        )
    owner = tmp_path / "owner"
    with pytest.raises(ValueError, match="REPARSE"):
        prepare(
            owner,
            tmp_path / "not-read.json",
            tmp_path / "not-read.parquet",
            owner / "forest",
            alias,
        )
    assert not owner.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_extra_retained_junction_rejected_before_traversal(tmp_path):
    from competition_tools.evaluation.forest_study import _retained_records

    output = tmp_path / "retained"
    output.mkdir()
    target = tmp_path / "external"
    target.mkdir()
    (target / "input.txt").write_text("external")
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(output / "alias"), str(target)],
        check=True,
        capture_output=True,
    )
    with pytest.raises(ValueError, match="REPARSE"):
        _retained_records(output)
