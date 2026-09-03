import json
from pathlib import Path


def test_competition_config_is_explicit_and_paper_safe():
    config = json.loads(
        Path("config/competition-2026-hk.json").read_text(encoding="utf-8")
    )
    assert config["market"] == "HK"
    assert config["benchmark"] == "HSCI"
    assert config["execution"]["environment"] == "paper"
    assert config["execution"]["dry_run"] is True
    assert config["eligibility"]["min_holding_rate"] == 0.5
