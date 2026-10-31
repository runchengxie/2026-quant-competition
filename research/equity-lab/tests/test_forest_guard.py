"""Synthetic owner budgets, blocked coverage and hard worker termination."""

import json
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
import pandas as pd
import pytest
from equity_lab.predictive.forest_study import fit_block
from equity_lab.predictive.protocol import Budget


def frames():
    dates = [f"2026-02-{i:02}" for i in range(1, 22)]
    rows = [
        dict(
            date=d,
            candidate_id=f"S{j}",
            target=j / 100,
            **{
                f: j / 10
                for f in [
                    "session_return",
                    "range_fraction",
                    "relative_dollar_volume",
                    "median_spread",
                    "quote_fraction",
                    "active_fraction",
                ]
            },
        )
        for d in dates
        for j in range(55)
    ]
    frame = pd.DataFrame(rows)
    return frame, dates


def test_failed_starts_are_durable_and_never_retried(tmp_path):
    frame, dates = frames()
    log = tmp_path / "attempts.jsonl"
    budget = Budget(log, max_attempts=2)

    def fail(kind, params, x, y):
        assert log.read_text().count("\n") in (1, 2)
        raise ValueError("synthetic failure")

    result, predictions = fit_block(
        frame, frame, frame, frame, dates, budget, 5, dates[0], fit=fail
    )
    assert result["status"] == "unavailable"
    assert predictions is None
    assert len(result["candidates"]) == 2
    assert all(c["status"] == "failed" for c in result["candidates"])
    assert len(log.read_text().splitlines()) == 2
    with pytest.raises(RuntimeError, match="budget"):
        budget.begin({})
    with pytest.raises(FileExistsError):
        Budget(log, max_attempts=6)


def test_constant_forecast_cannot_select_a_refit(tmp_path):
    frame, dates = frames()

    class Constant:
        def predict(self, x):
            return np.zeros(len(x))

    budget = Budget(tmp_path / "attempts.jsonl", max_attempts=6)
    result, predictions = fit_block(
        frame,
        frame,
        frame,
        frame,
        dates,
        budget,
        20,
        dates[0],
        fit=lambda *args: Constant(),
    )
    assert predictions is None
    assert result["status"] == "unavailable"
    assert budget.attempts == 2


def test_tie_selects_declared_depth_and_reserves_refit(tmp_path):
    frame, dates = frames()

    class Linear:
        def predict(self, x):
            return x[:, 0] / 10

    budget = Budget(tmp_path / "attempts.jsonl", max_attempts=6)
    result, predictions = fit_block(
        frame,
        frame,
        frame,
        frame,
        dates,
        budget,
        5,
        dates[0],
        fit=lambda *args: Linear(),
    )
    assert result["params"] == {"max_depth": 3}
    assert result["status"] == "completed"
    assert len(predictions) == len(frame)
    attempts = [json.loads(s) for s in budget.path.read_text().splitlines()]
    assert [r["condition"]["phase"] for r in attempts] == [
        "validation",
        "validation",
        "refit",
    ]


def test_hard_deadline_terminates_sleeping_worker():
    from equity_lab.predictive.forest_study_cli import bounded

    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        bounded([sys.executable, "-c", "import time; time.sleep(60)"], 0.5)
    assert time.monotonic() - started < 10


def test_failed_horizon_reports_every_missing_account_cell():
    from equity_lab.predictive.forest_study_cli import missing_cells

    binding = dict(
        rules=dict(windows=[["2026-05-28", "2026-07-24"], ["2026-07-27", "2026-09-21"]])
    )
    report = dict(accounts=[])
    cells = missing_cells(binding, report, 5, "deadline")
    assert len(cells) == 48
    assert all(row["reason"] == "deadline" for row in cells)
    report["accounts"].append(cells[0])
    assert len(missing_cells(binding, report, 5, "deadline")) == 47
    assert len(missing_cells(binding, report, 20, "deadline")) == 48


def test_failed_aggregate_counts_owner_starts_when_output_mirror_is_missing(tmp_path):
    from equity_lab.predictive.forest_study_cli import authoritative_attempt_count

    reservation = tmp_path / "reservation.json"
    owner_log = Path(str(reservation) + ".h5.attempts.jsonl")
    owner_log.write_text('{"attempt":1}\n{"attempt":2}\n')
    assert authoritative_attempt_count(reservation, 5) == 2
    assert authoritative_attempt_count(reservation, 20) == 0
    # A partially persisted reserved start remains conservatively consumed.
    owner_log.write_text('{"attempt":1}\n{"attempt":')
    assert authoritative_attempt_count(reservation, 5) == 2


def test_default_real_study_cannot_fit_or_create_output_without_claim(tmp_path):
    from equity_lab.predictive.forest_study import run_forest_study

    output = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="CLAIM_REQUIRED"):
        run_forest_study(None, None, output, {})
    assert not output.exists()


def test_owner_claim_blocks_hidden_worker_output_reset(tmp_path, monkeypatch):
    import hashlib
    from equity_lab.predictive.forest_study_guard import start_forest, claim_horizon
    from equity_lab.run_guard import source_digest, lock_digest, digest

    source = tmp_path / "input.parquet"
    source.write_bytes(b"synthetic")
    owner = tmp_path / "owner"
    folder = owner / "research-reservations"
    folder.mkdir(parents=True)
    key = dict(
        protocol="equity.low_turnover_forest.20261031.v1", input_sha256=digest(source)
    )
    filename = (
        hashlib.sha256(
            json.dumps(key, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        + ".json"
    )
    path = folder / filename
    binding = dict(
        **key, binding_sha256="a" * 64, output=str(owner / "results"), owner=str(owner)
    )
    receipt = dict(
        schema="competition.research_reservation.v1",
        status="reserved",
        owner_root=str(owner),
        output=binding["output"],
        identity=dict(
            **key,
            code_sha256=source_digest(),
            lock_sha256=lock_digest(),
            binding_sha256="a" * 64,
        ),
    )
    path.write_text(json.dumps(receipt))
    Path(str(path) + ".started").write_text("{}")
    token = start_forest(path, binding)
    with pytest.raises(ValueError, match="TOKEN"):
        claim_horizon(path, binding, 5)
    monkeypatch.setenv("GMR_FOREST_WORKER_TOKEN", token)
    claim_horizon(path, binding, 5)
    with pytest.raises(FileExistsError):
        claim_horizon(path, binding, 5)
    binding["output"] = str(owner / "reset")
    binding["binding_sha256"] = "b" * 64
    receipt["output"] = binding["output"]
    receipt["identity"]["binding_sha256"] = "b" * 64
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="START"):
        claim_horizon(path, binding, 20)
    assert not (owner / "reset").exists()
