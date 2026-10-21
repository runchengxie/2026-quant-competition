"""The module CLI publishes a new snapshot and consumes its exact manifest."""

import json
import pytest
from competition_tools.team.__main__ import main
from competition_tools.datasets.daily_storage import verify_daily_manifest
from test_daily_broker import run, Clock, Client


def test_module_plan_acquire_inspect_refresh(tmp_path, monkeypatch, capsys):
    spec, _, _, _ = run(tmp_path / "fixture", monkeypatch)
    clock = Clock()

    class Session:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return Client(clock)

        def __exit__(self, *a):
            pass

    from competition_tools.datasets import daily_broker, daily_refresh

    collect = daily_broker.collect_daily
    refresh = daily_refresh.refresh_daily
    monkeypatch.setattr(
        daily_broker,
        "collect_daily",
        lambda spec, staging: collect(
            spec, staging, session_factory=Session, clock=clock, sleep=clock.sleep
        ),
    )
    monkeypatch.setattr(
        daily_refresh,
        "refresh_daily",
        lambda spec, base, staging: refresh(
            spec, base, staging, session_factory=Session, clock=clock, sleep=clock.sleep
        ),
    )
    config = tmp_path / "team.toml"
    config.write_text(
        f'schema_version="competition.team.v1"\ndata_root="{tmp_path.as_posix()}"\nenvironment_root="{tmp_path.as_posix()}/envs"\n'
    )
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec))
    args = ["--config", str(config), "--spec", str(spec_file)]
    assert main(["data", "plan", *args]) == 0
    assert not (tmp_path / "2026-quant-competition").exists()
    capsys.readouterr()
    assert main(["data", "acquire", *args]) == 0
    result = json.loads(capsys.readouterr().out)
    from pathlib import Path

    parent = Path(result["projects"][0]["receipt"])
    assert verify_daily_manifest(parent)["coverage"]["SPY"]["bars"] == 4
    before = parent.read_bytes()
    assert main(["data", "inspect", *args, "--manifest", str(parent)]) == 0
    assert (
        json.loads(capsys.readouterr().out)["projects"][0]["schema"]
        == "competition.coverage_report.v2"
    )
    assert main(["data", "acquire", *args]) == 2
    capsys.readouterr()
    spec_file.write_text(json.dumps(spec | {"version": "v2"}))
    assert main(["data", "refresh", *args, "--base-manifest", str(parent)]) == 0
    child = Path(json.loads(capsys.readouterr().out)["projects"][0]["receipt"])
    assert verify_daily_manifest(child)["parent_manifest_sha256"] is not None
    assert parent.read_bytes() == before


def test_refresh_help_needs_no_configuration(capsys):
    with pytest.raises(SystemExit) as error:
        main(["data", "--help"])
    assert error.value.code == 0
    assert "--base-manifest" in capsys.readouterr().out
