"""Preparation and inspection are offline; CLI errors stay machine-readable."""

import json

from competition_tools.team.__main__ import main


def test_daily_extension_help_is_configuration_free(capsys):
    import pytest

    with pytest.raises(SystemExit) as exit:
        main(["daily-extension", "--help"])
    assert exit.value.code == 0
    assert "prepare" in capsys.readouterr().out


def test_prepare_missing_config_is_sanitized(tmp_path, capsys):
    code = main(["daily-extension", "prepare", "--config", str(tmp_path / "missing"), "--spec", str(tmp_path / "spec"), "--base-manifest", str(tmp_path / "parent"), "--output-root", str(tmp_path / "out")])
    assert code == 2
    value = json.loads(capsys.readouterr().out)
    assert value["status"] == "blocked"
    assert str(tmp_path) not in json.dumps(value)
