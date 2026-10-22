import subprocess

import pytest

from competition_tools.team.factors import load_factor_protocol, execute
from competition_tools.team.config import TeamConfig


def test_root_rejects_unknown_protocol(tmp_path):
    path = tmp_path / "protocol.json"
    path.write_text('{"schema":"unknown"}')
    with pytest.raises(ValueError, match="INVALID_FACTOR_PROTOCOL"):
        load_factor_protocol(path)


def test_child_environment_drops_provider_key(tmp_path, monkeypatch):
    from competition_tools.team import factors

    monkeypatch.setenv("DEXPAPRIKA_API_KEY", "fixture-only")
    value = {"manifest_file": str(tmp_path / "manifest.json")}
    monkeypatch.setattr(factors, "load_factor_protocol", lambda _: value)
    monkeypatch.setattr(
        factors, "verify_dex_manifest", lambda _: {"protocol_sha256": "a" * 64}
    )
    monkeypatch.setattr(factors, "digest", lambda _: "a" * 64)

    def child(argv, *, environment, timeout):
        assert "DEXPAPRIKA_API_KEY" not in {k.upper() for k in environment}
        assert "fixture-only" not in str(argv)
        return subprocess.CompletedProcess(argv, 2, "", "")

    monkeypatch.setattr(factors, "run_child", child)
    result = execute(
        TeamConfig(tmp_path / "data", tmp_path / "envs"),
        tmp_path / "protocol.json",
        tmp_path / "out",
    )
    assert result["issue_codes"] == ["FACTOR_CHILD_FAILED"]
