"""Causal scores and durable bounds, without fitting retained real inputs."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import pytest

from equity_lab.predictive.tree_study import momentum_scores, fit_block
from equity_lab.predictive.protocol import Budget


def history():
    sessions = (
        pd.date_range("2026-01-01", periods=25, freq="B").strftime("%Y-%m-%d").tolist()
    )
    base = pd.DataFrame(
        dict(
            date=sessions,
            candidate_id="A",
            ticker="AAA",
            close_price=np.arange(100.0, 125.0),
            price_valid=True,
            action_boundary=False,
        )
    )
    return base, sessions


def test_momentum_uses_completed_twenty_session_change_and_rejects_gaps():
    base, sessions = history()
    scores = momentum_scores(base, sessions)
    assert pd.isna(scores.iloc[19])
    assert scores.iloc[20] == pytest.approx(0.2)
    base.loc[24, "close_price"] = 100000
    assert momentum_scores(base, sessions).iloc[20] == pytest.approx(0.2)
    assert pd.isna(momentum_scores(base.drop(index=5), sessions).iloc[19])


@pytest.mark.parametrize(
    "column,value",
    [("action_boundary", True), ("ticker", "OTHER"), ("price_valid", False)],
)
def test_momentum_rejects_action_identity_and_price_breaks(column, value):
    base, sessions = history()
    base.loc[5, column] = value
    assert pd.isna(momentum_scores(base, sessions).iloc[20])


@pytest.mark.parametrize("ticker", ["", " ", "nan", "None", None])
def test_momentum_rejects_missing_ticker_identity(ticker):
    base, sessions = history()
    base["ticker"] = ticker
    assert pd.isna(momentum_scores(base, sessions).iloc[20])


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
    assert result["params"] == {"max_depth": 2}
    assert result["status"] == "completed"
    assert len(predictions) == len(frame)
    attempts = [json.loads(s) for s in budget.path.read_text().splitlines()]
    assert [r["condition"]["phase"] for r in attempts] == [
        "validation",
        "validation",
        "refit",
    ]


def test_hard_deadline_terminates_sleeping_worker():
    from equity_lab.predictive.tree_study_cli import bounded

    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        bounded([sys.executable, "-c", "import time; time.sleep(60)"], 0.5)
    assert time.monotonic() - started < 10


def test_failed_horizon_reports_every_missing_account_cell():
    from equity_lab.predictive.tree_study_cli import missing_cells

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
    from equity_lab.predictive.tree_study_cli import authoritative_attempt_count

    reservation = tmp_path / "reservation.json"
    owner_log = Path(str(reservation) + ".h5.attempts.jsonl")
    owner_log.write_text('{"attempt":1}\n{"attempt":2}\n')
    assert authoritative_attempt_count(reservation, 5) == 2
    assert authoritative_attempt_count(reservation, 20) == 0
    # A partially persisted reserved start remains conservatively consumed.
    owner_log.write_text('{"attempt":1}\n{"attempt":')
    assert authoritative_attempt_count(reservation, 5) == 2


def test_default_real_study_cannot_fit_or_create_output_without_claim(tmp_path):
    from equity_lab.predictive.tree_study import run_tree_study

    output = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="CLAIM_REQUIRED"):
        run_tree_study(None, None, output, {})
    assert not output.exists()


def test_owner_claim_blocks_hidden_worker_output_reset(tmp_path, monkeypatch):
    import hashlib
    from equity_lab.predictive.tree_study_guard import start_tree, claim_horizon
    from equity_lab.run_guard import source_digest, lock_digest, digest

    source = tmp_path / "input.parquet"
    source.write_bytes(b"synthetic")
    owner = tmp_path / "owner"
    folder = owner / "research-reservations"
    folder.mkdir(parents=True)
    key = dict(
        protocol="equity.low_turnover_tree.20261031.v1", input_sha256=digest(source)
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
    token = start_tree(path, binding)
    with pytest.raises(ValueError, match="TOKEN"):
        claim_horizon(path, binding, 5)
    monkeypatch.setenv("GMR_TREE_WORKER_TOKEN", token)
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


def test_complete_new_artifacts_pass_independent_root_and_tampering_fails(
    tmp_path, monkeypatch
):
    """Keep accounting/splits/metrics real; replace only estimator training.

    This exercises 168 reused + 96 new account paths on synthetic prices. The
    root process has no leaf dependencies and independently reconstructs scores.
    """
    python = os.environ.get("GMR_TREE_ROOT_PYTHON")
    if not python:
        pytest.skip(
            "Set GMR_TREE_ROOT_PYTHON to the independently installed root interpreter"
        )
    import exchange_calendars as xcals
    from test_predictive_holding import raw_fixture
    from equity_lab.predictive import holding
    from equity_lab.predictive.tree_study import run_tree_study, write, bind_prepared
    from equity_lab.run_guard import digest

    tmp_path = tmp_path / "2026-quant-competition"
    tmp_path.mkdir()
    schedule = xcals.get_calendar(
        "XNYS", start="2025-09-25", end="2026-10-20"
    ).schedule[["open", "close"]]
    raw, previous = raw_fixture(len(schedule), 55)
    mapping = dict(zip(previous.index, schedule.index, strict=True))
    raw["TradeDate"] = raw.TradeDate.map(mapping)
    # One known boundary forces blocked paths; no replacement or stitching.
    raw["KnownActionBoundary"] = (raw.ResearchKey == "unresolved:S000") & (
        raw.TradeDate == schedule.index[-90]
    )

    class Linear:
        def predict(self, x):
            return x[:, 0]

    monkeypatch.setattr(holding, "fit_model", lambda *args: Linear())
    parent = tmp_path / "parent"
    parent.mkdir()
    source = parent / "daily.parquet"
    raw.to_parquet(source, index=False)
    old = holding.run_holding(raw, schedule, parent / "equity", profile="validation60")
    old.update(
        protocol="equity.holding_validation60.20261025.v1",
        input_sha256=digest(source),
        source_unchanged=True,
    )
    write(parent / "equity/report.json", old)
    changed = raw.copy()
    changed.loc[0, "close_price"] *= 1.001
    with pytest.raises(AssertionError):
        bind_prepared(changed, schedule, parent / "equity")
    root = Path(__file__).resolve().parents[3]
    # Freeze an actual run record using a tiny committed synthetic source tree.
    # The new protocol binds the real current implementation separately.
    program = r"""
import json, sys, subprocess
from pathlib import Path
from competition_tools.evaluation.run_record import freeze_run, finish_run, OWNER
from competition_tools.evaluation.tree_study import prepare, verify_binding, run
from competition_tools.evaluation.research_reservation import validate_reservation
base, source = map(Path, sys.argv[1:])
parent = base / 'parent'
repo = base / 'synthetic-source'
for directory in ('src','research/equity-lab/src','research/crypto-mm/src'):
    (repo/directory).mkdir(parents=True)
    (repo/directory/'fixture.py').write_text('VALUE=1\n')
for directory in ('.','research/equity-lab','research/crypto-mm'):
    for name in ('pyproject.toml','uv.lock'):
        (repo/directory/name).write_text('# synthetic\n')
for args in (['init'], ['add','.'], ['-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','synthetic']):
    subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)
(parent/'.workflow-run').write_text(OWNER)
freeze_run(repo,parent,['daily.parquet'],{'synthetic':True})
finish_run(parent,[p.relative_to(parent).as_posix() for p in (parent/'equity').iterdir()],status='completed',environments={'synthetic':True})
result=prepare(base/'owner',parent,parent/'equity',parent/'daily.parquet',base/'owner/results/tree',source)
binding=verify_binding(result['protocol'])
receipt=json.loads(Path(result['reservation']).read_text())
validate_reservation(result['reservation'],receipt['identity'],result['output'])
try:
    prepare(base/'owner',parent,parent/'equity',parent/'daily.parquet',base/'owner/results/second',source)
except FileExistsError:
    pass
else:
    raise AssertionError('same input/protocol reset the reservation')
Path(result['reservation']+'.started').write_text('{}')
try:
    run(result['protocol'],result['reservation'],Path('must-never-launch'))
except ValueError:
    pass
else:
    raise AssertionError('consumed reservation restarted')
(base/'prepared.json').write_text(json.dumps(result))
"""
    completed = subprocess.run(
        [python, "-c", program, str(tmp_path), str(root)],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    prepared = json.loads((tmp_path / "prepared.json").read_text())
    binding = json.loads(Path(prepared["protocol"]).read_text())
    output = Path(prepared["output"])
    from equity_lab.predictive.tree_study_guard import start_tree, claim_horizon

    monkeypatch.setenv(
        "GMR_TREE_WORKER_TOKEN", start_tree(prepared["reservation"], binding)
    )
    output.mkdir(parents=True)
    parts = []
    for h in (5, 20):
        claim = claim_horizon(prepared["reservation"], binding, h)
        parts.append(
            run_tree_study(
                raw,
                schedule,
                output / f"h{h}",
                binding,
                fit=lambda *args: Linear(),
                horizons=(h,),
                claim=claim,
            )
        )
    report = {
        k: v
        for k, v in parts[0].items()
        if k not in ("models", "accounts", "fit_attempts")
    }
    report.update(
        status="completed",
        unavailable_cells=[],
        new_requested_accounts=96,
        models=[m for p in parts for m in p["models"]],
        accounts=[a for p in parts for a in p["accounts"]],
        fit_attempts=sum(p["fit_attempts"] for p in parts),
        horizons=[dict(horizon=h, status="completed", reason=None) for h in (5, 20)],
    )
    write(output / "report.json", report)
    program = r"""
import json, sys
from pathlib import Path
from competition_tools.evaluation.tree_study import verify_binding
from competition_tools.evaluation.tree_study_validation import verify
path=Path(sys.argv[1]); binding=verify_binding(path)
result=verify(path)
assert result['fit_attempts']==12
assert result['new_requested_accounts']==96
assert result['blocked_new_accounts']>0
assert len(result['paired']['returns'])==432
assert len(result['paired']['rank_ic'])==24
output=Path(binding['output']); parent=Path(binding['parent_equity'])
# Parent change, missing binding, validation scores, selected score, plans,
# cash ledger and report metrics must each fail independently.
targets=[parent/'decisions.csv', output/'h5/h5-2026-05-28-depth2-validation.csv',
         output/'h5/h5-2026-05-28-shallow_tree-predictions.csv',
         output/'h5/h5-2026-05-28-momentum20-predictions.csv',
         output/'h5/h5-2026-05-28-shallow_tree-b0-plans.json',
         output/'h5/h5-2026-05-28-shallow_tree-b0-f20-d0.json',output/'report.json']
for target in targets:
    body=target.read_bytes()
    if target.suffix=='.csv':
        lines=body.decode().splitlines(); fields=lines[1].split(','); fields[-1]='999'; lines[1]=','.join(fields)
        target.write_text('\n'.join(lines)+'\n')
    else:
        value=json.loads(body)
        if target.name.endswith('plans.json'):
            value[0]['selected']=[]
        elif target.name=='report.json':
            value['accounts'][0]['metrics']={'net_return':999}
        else:
            value['net']['periods'][0]['cash']=999
        target.write_text(json.dumps(value))
    try:
        verify(path)
    except (ValueError, KeyError, TypeError):
        pass
    else:
        raise AssertionError('accepted tampered '+target.name)
    finally:
        target.write_bytes(body)
(output/'verification.json').write_text(json.dumps(result))
from jsonschema import Draft202012Validator
schema=json.loads((Path(sys.argv[2])/'schemas/research/low-turnover-tree.v1.schema.json').read_text())
Draft202012Validator(schema).validate(result)
tampered=json.loads(json.dumps(result)); tampered['paired']['returns'][0]['difference']=999
(output/'verification.json').write_text(json.dumps(tampered))
try:
    verify(path)
except ValueError:
    pass
else:
    raise AssertionError('accepted changed paired verification summary')
(output/'verification.json').write_text(json.dumps(result))
body=(output/'report.json').read_bytes()
logs={h:(output/f'h{h}/attempts-{h}.jsonl').read_bytes() for h in (5,20)}
changed=json.loads(body)
for h in (5,20):
    starts=[json.loads(s) for s in logs[h].decode().splitlines()]
    refits=[r for r in starts if r['condition']['phase']=='refit']
    for index,row in enumerate(refits,1): row['attempt']=index
    (output/f'h{h}/attempts-{h}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in refits))
    for row in changed['models']:
        if row['horizon']==h and row['model']=='shallow_tree':
            for candidate in row['candidates']: candidate['attempt']=None
            row['refit_attempt']=next(r['attempt'] for r in refits if r['condition']['fold']==row['window'])
changed['fit_attempts']=4
(output/'report.json').write_text(json.dumps(changed))
changed_summary=json.loads(json.dumps(result)); changed_summary['fit_attempts']=4
(output/'verification.json').write_text(json.dumps(changed_summary))
try:
    verify(path)
except ValueError:
    pass
else:
    raise AssertionError('completed validation fits accepted without durable starts')
finally:
    (output/'report.json').write_bytes(body)
    (output/'verification.json').write_text(json.dumps(result))
    for h,content in logs.items(): (output/f'h{h}/attempts-{h}.jsonl').write_bytes(content)
for index,key,value in [(0,'end','2026-07-23'),(1,'end','2026-07-23'),(1,'status','failed')]:
    changed=json.loads(body); changed['models'][index][key]=value
    (output/'report.json').write_text(json.dumps(changed))
    try:
        verify(path)
    except ValueError:
        pass
    else:
        raise AssertionError('accepted changed model metadata')
    finally:
        (output/'report.json').write_bytes(body)
# A recorded move preserves immutable protocol bytes and their digest.
from competition_tools.evaluation.study_identity import canonical_hash
import subprocess
receipt_path=Path(sys.argv[3]); original_protocol=path.read_bytes(); original_receipt=receipt_path.read_bytes()
forged=json.loads(original_protocol); forged['output']=str(output.parent/'hidden-reset')
forged['binding_sha256']=canonical_hash({k:v for k,v in forged.items() if k!='binding_sha256'})
receipt=json.loads(original_receipt); receipt['output']=forged['output']; receipt['identity']['binding_sha256']=forged['binding_sha256']
path.write_text(json.dumps(forged)); receipt_path.write_text(json.dumps(receipt))
try:
    hidden=subprocess.run([sys.argv[4],'-m','equity_lab.predictive.tree_study_cli','--horizon','5',
        '--input',binding['input'],'--output',str(Path(forged['output'])/'h5'),
        '--reservation',str(receipt_path)],capture_output=True,text=True)
    assert hidden.returncode!=0, 'hidden worker reset consumed reservation'
    assert not Path(forged['output']).exists(), 'hidden worker created reset output'
finally:
    path.write_bytes(original_protocol); receipt_path.write_bytes(original_receipt)
legacy=Path(binding['parent_run']).parent
canonical=legacy.parent/'global-market-research'
frozen=path.read_bytes()
legacy.rename(canonical)
(canonical/'.storage-migration.json').write_text(json.dumps(dict(schema='competition.storage_migration.v1',
    legacy_root=str(legacy),canonical_root=str(canonical),phase='completed',inventory_sha256='0'*64)))
moved=canonical/path.relative_to(legacy)
assert moved.read_bytes()==frozen
assert verify(path)==result
"""
    completed = subprocess.run(
        [
            python,
            "-c",
            program,
            prepared["protocol"],
            str(root),
            prepared["reservation"],
            sys.executable,
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
