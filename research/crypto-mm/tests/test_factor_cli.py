import json
import subprocess
import sys

import pytest

from crypto_mm.factors.study import run_factor_study
from test_factor_inputs import create_inputs


def test_factor_study_reports_descriptive_counts(tmp_path):
    protocol = create_inputs(tmp_path)
    result = run_factor_study(protocol, tmp_path / "output")
    assert result["schema"] == "competition.dex_factor_result.v1"
    assert len(result["time_series"]) == 16
    assert len(result["cross_sectional"]) == 16
    record = next(
        r
        for r in result["time_series"]
        if r["signal_id"] == "momentum_24h"
        and r["horizon"] == 6
        and r["sampling"] == "all_valid"
    )
    assert record["overall"]["n"] == 210
    assert [r["n"] for r in record["slices"]] == [210, 0, 0]
    nonoverlap = next(
        r
        for r in result["time_series"]
        if r["signal_id"] == "momentum_24h"
        and r["horizon"] == 6
        and r["sampling"] == "non_overlapping"
    )
    assert nonoverlap["overall"]["n"] == 35
    assert all(
        r["reason"] == "INSUFFICIENT_UNDERLYINGS" for r in result["cross_sectional"]
    )
    assert "pnl" not in result
    assert result["restrictions"]


def test_source_mutation_invalidates_result(tmp_path, monkeypatch):
    from crypto_mm.factors import study

    protocol = create_inputs(tmp_path)
    original = study.build_signals

    def changed(*args):
        result = original(*args)
        (tmp_path / "dataset/normalized.json").write_text("[]")
        return result

    monkeypatch.setattr(study, "build_signals", changed)
    with pytest.raises(ValueError, match="FACTOR_INPUT_HASH_MISMATCH"):
        run_factor_study(protocol, tmp_path / "output")
    assert not (tmp_path / "output/result.json").exists()


def test_actual_leaf_cli(tmp_path):
    value = create_inputs(tmp_path)
    spec = tmp_path / "protocol.json"
    spec.write_text(json.dumps(value))
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "crypto_mm.factors",
            "--spec",
            str(spec),
            "--output-root",
            str(tmp_path / "cli-output"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout)["status"] == "completed"


@pytest.mark.parametrize("all_constant", [False, True])
def test_constant_cross_targets_keep_groups_and_use_separate_ic_count(
    tmp_path, monkeypatch, all_constant
):
    from crypto_mm.factors import study

    assets = [str(i) for i in range(9)]
    protocol = dict(
        dataset=dict(
            start="2025-01-01T00:00:00Z", assets=[{"stable_id": a} for a in assets]
        ),
        signals=["momentum_24h"],
        horizons=[6],
        sampling=["all_valid"],
        source_commit="a" * 40,
        source_files=[],
    )
    inputs = dict(
        rows={a: [int(a)] for a in assets},
        manifest_sha256="m",
        protocol_sha256="p",
        input_hashes=[],
        code_hashes=[],
    )
    monkeypatch.setattr(study, "verify_inputs", lambda _: inputs)

    def series(values):
        return [
            {"timestamp": f"2025-01-01T0{i}:00:00Z", "value": v}
            for i, v in enumerate(values)
        ]

    monkeypatch.setattr(study, "build_signals", lambda rows, _: series([rows[0]] * 3))
    monkeypatch.setattr(
        study,
        "forward_returns",
        lambda rows, _: series([0, 0 if all_constant else rows[0], 0]),
    )
    record = study.run_factor_study(protocol, tmp_path / "mixed")["cross_sectional"][0]
    assert record["valid_timestamps"] == 3
    assert record["ic_valid_timestamps"] == (0 if all_constant else 1)
    assert record["ic_excluded_reasons"] == {
        "CONSTANT_TARGET": 3 if all_constant else 2
    }
    assert record["mean_rank_ic"] == (None if all_constant else 1)
    assert record["ic_reason"] == ("CONSTANT_TARGET" if all_constant else None)
    assert record["group_mean_forward_returns"] == (
        [0, 0, 0] if all_constant else [1 / 3, 4 / 3, 7 / 3]
    )
