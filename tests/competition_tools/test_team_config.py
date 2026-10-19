"""Portable team configuration must work without maintainer settings."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from competition_tools.team.config import init_config, load_config
from competition_tools.team.paths import validate_external


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("module", [False, True])
def test_help_without_personal_config(tmp_path, module):
    env = os.environ.copy()
    env.update(
        HOME=str(tmp_path), USERPROFILE=str(tmp_path), PYTHONPATH=str(ROOT / "src")
    )
    env.pop("WORKSPACE_CONFIG", None)
    command = ["-m", "competition_tools.team"] if module else [str(ROOT / "team.py")]
    result = subprocess.run(
        [sys.executable, *command, "--help"],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""


def test_round_trip_and_exclusive_creation(tmp_path):
    config = tmp_path / "private" / "team.toml"
    expected = init_config(config, tmp_path / 'data with "quotes"')
    assert load_config(config) == expected
    assert (
        expected.environment_root
        == expected.data_root / "2026-quant-competition/environments"
    )
    before = config.read_bytes()
    with pytest.raises(ValueError):
        init_config(config, tmp_path / "other")
    assert config.read_bytes() == before


@pytest.mark.parametrize("marker", ["file", "directory"])
def test_refuse_git_source(tmp_path, marker):
    source = tmp_path / "source"
    source.mkdir()
    if marker == "file":
        (source / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    else:
        (source / ".git").mkdir()
    with pytest.raises(ValueError):
        validate_external(source / "nested" / "data")
    with pytest.raises(ValueError):
        init_config(source / "team.toml", tmp_path / "data")


def test_refuse_source_symlink(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / ".git").mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(source, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symbolic links is unavailable on this host")
    with pytest.raises(ValueError):
        validate_external(alias / "data")


@pytest.mark.parametrize("value", ["", "relative/data"])
def test_refuse_non_absolute_paths(value):
    with pytest.raises(ValueError):
        validate_external(Path(value))


def test_refuse_file_parent(tmp_path):
    parent = tmp_path / "file"
    parent.write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError):
        init_config(tmp_path / "team.toml", parent / "data")


@pytest.mark.parametrize(
    "text",
    [
        "[broken",
        'schema_version="unknown"',
        'schema_version="competition.team.v1"\ndata_root=""\nenvironment_root=""',
        'schema_version="competition.team.v1"\ndata_root="/tmp/data"\nenvironment_root="/tmp/env"\nextra=true',
    ],
)
def test_reject_invalid_configuration(tmp_path, text):
    path = tmp_path / "team.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)
