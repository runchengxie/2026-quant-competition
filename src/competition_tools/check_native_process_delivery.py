"""Measure only fixed synthetic PowerShell children, never Gateway or Java."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from .datasets.daily_storage import safe_path
from .datasets.storage import write_json
from .team.processes import run_child


def classify_process(*, started: bool, exit_code: int | None, observation_expired: bool, outer_expired: bool) -> dict:
    status = "outer_timeout" if outer_expired else "start_failed" if not started else "observation_timeout" if observation_expired else "completed" if exit_code == 0 else "child_failed"
    return dict(schema="competition.synthetic_process_diagnostic.v1",status=status,exit_code=exit_code,synthetic=True,outer_expired=outer_expired)


def measure_synthetic_process(output: Path, *, timeout_seconds: int, mode="success") -> dict:
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 20 or mode not in {"success","exit7","sleep","start-failure"}:
        raise ValueError("INVALID_SYNTHETIC_PROCESS_PARAMETERS")
    out=safe_path(output)
    out.mkdir(parents=True,exist_ok=False)
    wrapper=Path(__file__).resolve().parents[2] / "scripts/windows/Measure-SyntheticProcess.ps1"
    pwsh=shutil.which("pwsh")
    timing={}
    if pwsh is None:
        value=classify_process(started=False,exit_code=None,observation_expired=False,outer_expired=False)
    else:
        try:
            environment={k:v for k,v in os.environ.items() if k.upper() in {"PATH","SYSTEMROOT","WINDIR","TEMP","TMP","HOME","USERPROFILE","PATHEXT"}}
            child=run_child([pwsh,"-NoLogo","-NoProfile","-NonInteractive","-File",str(wrapper),"-OutputRoot",str(out / "native"),"-TimeoutSeconds",str(timeout_seconds),"-Mode",mode],environment=environment,timeout=20)
            if child.returncode:
                value=classify_process(started=False,exit_code=None,observation_expired=False,outer_expired=False)
            else:
                timing=json.loads(child.stdout)
                value=classify_process(started=timing["started"],exit_code=timing["exit_code"],observation_expired=timing["observation_expired"],outer_expired=False)
        except subprocess.TimeoutExpired:
            value=classify_process(started=False,exit_code=None,observation_expired=False,outer_expired=True)
    value.update({k:timing[k] for k in ("started_at","exited_at","observed_at","launch_seconds","redirection_seconds","wall_seconds") if k in timing})
    write_json(out / "diagnostic.json",value)
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root",type=Path,required=True)
    parser.add_argument("--timeout-seconds",type=int,default=10)
    args=parser.parse_args()
    value=measure_synthetic_process(args.output_root,timeout_seconds=args.timeout_seconds)
    print(json.dumps(value))
    return 0 if value["status"]=="completed" else 2


if __name__=="__main__":
    raise SystemExit(main())
