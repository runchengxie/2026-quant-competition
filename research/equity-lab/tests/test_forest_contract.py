"""Synthetic owner budgets, blocked coverage and hard worker termination."""

import json
import os
from pathlib import Path
import subprocess
import sys
import pytest


def test_complete_forest_saved_workflow_and_tampering(tmp_path, monkeypatch):
    """Keep accounting/splits/metrics real; replace only estimator training.

    This exercises 264 reused + 96 new account paths on synthetic prices. The
    root process has no leaf dependencies and independently reconstructs scores.
    """
    python = os.environ.get("GMR_FOREST_ROOT_PYTHON")
    if not python:
        pytest.skip(
            "Set GMR_FOREST_ROOT_PYTHON to the independently installed root interpreter"
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
from competition_tools.evaluation.forest_study import prepare, verify_binding
from competition_tools.evaluation.tree_study import read as tree_read
from competition_tools.evaluation.tree_study_validation import verify
base, tree_protocol, source = map(Path, sys.argv[1:])
assert verify(tree_protocol)['fit_attempts']==12
tree_output=Path(tree_read(tree_protocol)['output'])
extra=tree_output/'extra-unbound-input.csv'
try:
    extra.symlink_to(base/'parent/daily.parquet')
except OSError:
    pass
else:
    try:
        prepare(base/'must-not-reserve',tree_protocol,base/'parent/daily.parquet',base/'must-not-reserve/forest',source)
    except ValueError:
        assert not (base/'must-not-reserve').exists()
    else:
        raise AssertionError('extra retained symlink accepted before reservation')
    finally:
        extra.unlink()
result=prepare(base/'owner',tree_protocol,base/'parent/daily.parquet',base/'owner/results/forest',source)
verify_binding(result['protocol'])
try:
    prepare(base/'owner',tree_protocol,base/'parent/daily.parquet',base/'owner/results/forest-reset',source)
except FileExistsError:
    pass
else:
    raise AssertionError('forest reservation reset')
Path(result['reservation']+'.started').write_text('{}')
(base/'forest-prepared.json').write_text(json.dumps(result))
"""
    completed = subprocess.run(
        [python, "-c", program, str(tmp_path), prepared["protocol"], str(root)],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    prepared = json.loads((tmp_path / "forest-prepared.json").read_text())
    binding = json.loads(Path(prepared["protocol"]).read_text())
    output = Path(prepared["output"])
    from equity_lab.predictive.forest_study import run_forest_study
    from equity_lab.predictive.forest_study_guard import start_forest, claim_horizon

    monkeypatch.setenv(
        "GMR_FOREST_WORKER_TOKEN", start_forest(prepared["reservation"], binding)
    )
    output.mkdir(parents=True)
    parts = []
    for h in (5, 20):
        claim = claim_horizon(prepared["reservation"], binding, h)
        parts.append(
            run_forest_study(
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
import json, sys, subprocess
from pathlib import Path
from competition_tools.evaluation.forest_study import verify_binding
from competition_tools.evaluation.forest_study_validation import verify
path=Path(sys.argv[1]); result=verify(path); binding=json.loads(path.read_text())
assert result['fit_attempts']==24
assert result['reused_requested_accounts']==264
assert result['combined_requested_accounts']==360
assert len(result['paired_returns'])==576
assert result['blocked_new_accounts']>0
# The first call above exercises the complete default independent consumer.
# Subsequent mutations affect only new output files; retain the independently
# verified binding while avoiding repeated old-account replays per mutation.
from competition_tools.evaluation import forest_study_validation as consumer
consumer.verify_binding=lambda *args, **kwargs: binding
output=Path(binding['output'])
targets=[output/'h5/h5-2026-05-28-random_forest-depth3-validation.csv',
         output/'h5/h5-2026-05-28-extra_trees-predictions.csv',
         output/'h5/h5-2026-05-28-random_forest-b0-plans.json',
         output/'h5/h5-2026-05-28-extra_trees-b0-f20-d0.json', output/'report.json',
         output/'h5/attempts-5.jsonl']
for target in targets:
    body=target.read_bytes()
    if target.suffix=='.csv':
        lines=body.decode().splitlines(); fields=lines[1].split(','); fields[-1]='999'; lines[1]=','.join(fields)
        target.write_text('\n'.join(lines)+'\n')
    elif target.suffix=='.jsonl':
        target.write_text('\n'.join(body.decode().splitlines()[1:])+'\n')
    else:
        value=json.loads(body)
        if target.name.endswith('plans.json'): value[0]['selected']=[]
        elif target.name=='report.json': value['models'][0]['params']={'max_depth':5}
        else: value['net']['periods'][0]['cash']=999
        target.write_text(json.dumps(value))
    try: verify(path)
    except (ValueError, KeyError, TypeError): pass
    else: raise AssertionError('accepted tampered '+target.name)
    finally: target.write_bytes(body)
from jsonschema import Draft202012Validator
schema=json.loads((Path(sys.argv[3])/'schemas/research/low-turnover-forest.v1.schema.json').read_text())
Draft202012Validator(schema).validate(result)
(output/'verification.json').write_text(json.dumps(result))
changed=json.loads(json.dumps(result)); changed['paired_returns'][0]['difference']=999
(output/'verification.json').write_text(json.dumps(changed))
try: verify(path)
except ValueError: pass
else: raise AssertionError('accepted changed paired result')
(output/'verification.json').write_text(json.dumps(result))
# Hidden worker cannot reuse a consumed claim, even with genuine input and source.
hidden=subprocess.run([sys.argv[2],'-m','equity_lab.predictive.forest_study_cli','--horizon','5',
    '--input',binding['input'],'--output',str(output/'h5'),'--reservation',sys.argv[4]],
    capture_output=True,text=True)
assert hidden.returncode!=0
"""
    completed = subprocess.run(
        [
            python,
            "-c",
            program,
            prepared["protocol"],
            sys.executable,
            str(root),
            prepared["reservation"],
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
