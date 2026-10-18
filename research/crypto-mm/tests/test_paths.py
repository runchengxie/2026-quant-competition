"""External data paths must not depend on checkout location or working directory."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from crypto_mm.paths import load_data_root


@pytest.fixture(autouse=True)
def clean_path_environment(monkeypatch):
    for name in ("WORKSPACE_CONFIG", "CONFIG_ROOT", "DATA_ROOT", "XDG_CONFIG_HOME"):
        monkeypatch.delenv(name, raising=False)


def test_workspace_file_maps_to_permanent_project_data(tmp_path, monkeypatch):
    config = tmp_path / "workspace.toml"
    data = tmp_path / "external-data"
    config.write_text(f'data_root = "{data.as_posix()}"\n', encoding="utf-8")
    monkeypatch.setenv("WORKSPACE_CONFIG", str(config))
    monkeypatch.chdir(tmp_path)
    assert load_data_root() == data / "2026-quant-competition" / "research" / "crypto-mm" / "raw_data"


@pytest.mark.parametrize("location", ["home", "xdg", "config_root"])
def test_discovers_default_configuration(tmp_path, monkeypatch, location):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    owner = tmp_path / ".config" / "quant-competition"
    if location == "xdg":
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
        owner = tmp_path / "xdg" / "quant-competition"
    elif location == "config_root":
        monkeypatch.setenv("CONFIG_ROOT", str(tmp_path / "owner"))
        owner = tmp_path / "owner"
    config = owner / "shared" / "workspace.toml"
    config.parent.mkdir(parents=True)
    config.write_text(f'data_root = "{tmp_path.as_posix()}"\n', encoding="utf-8")
    assert load_data_root() == tmp_path / "2026-quant-competition" / "research" / "crypto-mm" / "raw_data"


def test_explicit_config_overrides_default_location(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_ROOT", str(tmp_path / "missing-default"))
    config = tmp_path / "explicit.toml"
    config.write_text(f'data_root = "{tmp_path.as_posix()}"\n', encoding="utf-8")
    monkeypatch.setenv("WORKSPACE_CONFIG", str(config))
    assert load_data_root() == tmp_path / "2026-quant-competition" / "research" / "crypto-mm" / "raw_data"


def test_data_root_environment_overrides_missing_config(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_CONFIG", str(tmp_path / "missing.toml"))
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    assert load_data_root() == tmp_path / "2026-quant-competition" / "research" / "crypto-mm" / "raw_data"


def test_missing_config_reports_path_and_remedy(tmp_path, monkeypatch):
    config = tmp_path / "missing.toml"
    monkeypatch.setenv("WORKSPACE_CONFIG", str(config))
    with pytest.raises(ValueError, match="WORKSPACE_CONFIG") as exc:
        load_data_root()
    assert str(config) in str(exc.value)


@pytest.mark.parametrize("contents", ['other = "unused"', 'data_root = 123',
                                       'data_root = ""', 'data_root = "relative"',
                                       'data_root = ['])
def test_invalid_config_fails_without_checkout_fallback(tmp_path, monkeypatch, contents):
    config = tmp_path / "invalid.toml"
    config.write_text(contents, encoding="utf-8")
    monkeypatch.setenv("WORKSPACE_CONFIG", str(config))
    with pytest.raises(ValueError, match="data_root|TOML"):
        load_data_root()


def test_relative_environment_root_is_rejected(monkeypatch):
    monkeypatch.setenv("DATA_ROOT", "relative")
    with pytest.raises(ValueError, match="absolute"):
        load_data_root()


def test_config_consumers_use_external_data_without_local_link(tmp_path):
    data = tmp_path / "data"
    for dataset in ("orderbook", "trades", "fundings"):
        folder = data / "2026-quant-competition" / "research" / "crypto-mm" / "raw_data" / dataset
        folder.mkdir(parents=True)
        for day in ("19", "20", "21"):
            (folder / f"2026-03-{day}.parquet").touch()
    config = tmp_path / "workspace.toml"
    config.write_text(f'data_root = "{data.as_posix()}"\n', encoding="utf-8")
    env = {**os.environ, "WORKSPACE_CONFIG": str(config)}
    env.pop("DATA_ROOT", None)
    root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = str(root / "src")
    result = subprocess.run(
        [sys.executable, "-c", "from crypto_mm.data_files import dataset_files; "
         "from crypto_mm.config import DATA_ROOT; print(DATA_ROOT); "
         "print(sum(map(len, dataset_files().values())))"],
        cwd=tmp_path, env=env, capture_output=True, text=True, check=True,
    )
    assert result.stdout.splitlines() == [
        str(data / "2026-quant-competition" / "research" / "crypto-mm" / "raw_data"), "9"
    ]
