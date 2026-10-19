"""Doctor reports local readiness without importing providers or networking."""

import json

from competition_tools.team.config import TeamConfig
from competition_tools.team.doctor import diagnose


def test_doctor_missing_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("COINPAPRIKA_API_KEY", "credential-sentinel")
    value = diagnose(TeamConfig(tmp_path / "data", tmp_path / "environments"))
    assert value["status"] == "blocked"
    assert value["issue_codes"] == ["ENVIRONMENT_UNAVAILABLE"]
    assert len(value["projects"]) == 3
    assert value["synthetic"] is None
    assert "credential-sentinel" not in json.dumps(value)
