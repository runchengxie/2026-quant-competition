import json
import os
from pathlib import Path
import subprocess
import sys

import jsonschema
import pytest
from referencing import Registry, Resource

from competition_tools.datasets.databento_spec import pilot_spec
from competition_tools.team.config import TeamConfig
from competition_tools.team.data import execute


def test_team_databento_plan_offline_and_reject_refresh(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(pilot_spec(tmp_path / "missing.env")))
    config = TeamConfig(tmp_path / "data", tmp_path / "envs")
    result = execute("plan", config, spec)
    assert result["status"] == "completed"
    assert result["projects"][0]["accepted_research"] is False
    for action, kwargs in [
        ("refresh", {}),
        ("acquire", {"ensure_gateway": True}),
        ("acquire", {"base_manifest": tmp_path / "parent"}),
    ]:
        with pytest.raises(ValueError):
            execute(action, config, spec, **kwargs)


def test_real_cli_synthetic_delivery(tmp_path):
    root = Path(__file__).resolve().parents[2]
    config = tmp_path / "team.toml"
    config.write_text(
        'schema_version = "competition.team.v1"\n'
        + "data_root = "
        + json.dumps(str(tmp_path / "data"))
        + "\n"
        + "environment_root = "
        + json.dumps(str(tmp_path / "envs"))
        + "\n"
    )
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(pilot_spec(tmp_path / "synthetic.env")))
    script = """
import sys
sys.path.insert(0, sys.argv[1])
from test_databento_acquisition import FakeTransport
from competition_tools.datasets import databento_acquisition as a
from competition_tools.team.__main__ import main
a.DatabentoTransport=lambda *args,**kwargs: FakeTransport()
raise SystemExit(main(['data','acquire','--config',sys.argv[2],'--spec',sys.argv[3]]))
"""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    run = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(Path(__file__).parent),
            str(config),
            str(spec),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert run.returncode == 2, run.stderr
    result = json.loads(run.stdout)
    assert result["projects"][0]["status"] == "partial"
    path = Path(result["projects"][0]["manifest"])
    manifest = json.loads(path.read_text())
    resource = Resource.from_contents(
        json.loads(
            (root / "schemas/research/databento-dataset-spec.v1.json").read_text()
        )
    )
    schema = json.loads(
        (root / "schemas/research/databento-dataset-manifest.v1.json").read_text()
    )
    registry = Registry().with_resource("databento-dataset-spec.v1.json", resource)
    jsonschema.Draft202012Validator(schema, registry=registry).validate(manifest)
    bars = (path.parent / "normalized/SPY.csv").read_text().splitlines()
    assert bars[1].split(",")[1:] == ["100", "102", "99", "101", "1000"]
    inspected = subprocess.run(
        [
            sys.executable,
            "-m",
            "competition_tools.team",
            "data",
            "inspect",
            "--config",
            str(config),
            "--spec",
            str(spec),
            "--manifest",
            str(path),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert inspected.returncode == 2, inspected.stderr
    assert json.loads(inspected.stdout)["projects"][0]["accepted_research"] is False
