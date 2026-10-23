"""Native and optional research dispatch use separate installed interpreters."""

from pathlib import Path

from competition_tools.team.config import TeamConfig
from competition_tools.team.run import run_experiment


def test_run_requires_selected_environment(tmp_path):
    config = TeamConfig(tmp_path / "data", tmp_path / "env")
    value = run_experiment(
        "international", config, tmp_path / "experiment.yml", tmp_path / "new"
    )
    assert value["issue_codes"] == ["ENVIRONMENT_UNAVAILABLE"]
    assert value["synthetic"] is None


def test_run_refuses_existing_and_source_outputs(tmp_path):
    config = TeamConfig(tmp_path / "data", tmp_path / "env")
    assert run_experiment("international", config, tmp_path / "config.yml", tmp_path)[
        "issue_codes"
    ] == ["INVALID_OUTPUT"]
    source = tmp_path / "source"
    source.mkdir()
    (source / ".git").mkdir()
    assert run_experiment("next-open", config, tmp_path / "config.yml", source / "new")[
        "issue_codes"
    ] == ["INVALID_OUTPUT"]


def test_unknown_experiment_has_stable_result(tmp_path):
    config = TeamConfig(tmp_path / "data", tmp_path / "env")
    assert run_experiment("unknown", config, Path("no-config"), tmp_path / "new")[
        "issue_codes"
    ] == ["INVALID_PROJECT"]


def test_us_adapter_uses_an_independent_environment(tmp_path):
    config = TeamConfig(tmp_path / "data", tmp_path / "env")
    assert run_experiment(
        "us-next-session", config, tmp_path / "us.json", tmp_path / "new"
    )["issue_codes"] == ["ENVIRONMENT_UNAVAILABLE"]
