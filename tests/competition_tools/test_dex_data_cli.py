import json

import pytest

from competition_tools.team.config import TeamConfig
from competition_tools.team.data import execute
from test_dex_spec import sample


def config_spec(tmp_path):
    config = TeamConfig(tmp_path / "data", tmp_path / "envs")
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(sample(tmp_path)))
    return config, path


def test_dex_plan_uses_offline_namespace(tmp_path):
    config, spec = config_spec(tmp_path)
    result = execute("plan", config, spec)
    assert result["projects"][0]["schema"] == "competition.dex_plan.v1"
    assert not (tmp_path / "provider.env").exists()


def test_dex_refresh_and_gateway_rejected(tmp_path):
    config, spec = config_spec(tmp_path)
    with pytest.raises(ValueError, match="DEX_REFRESH_UNSUPPORTED"):
        execute("refresh", config, spec)
    with pytest.raises(ValueError, match="Gateway"):
        execute("acquire", config, spec, ensure_gateway=True)
