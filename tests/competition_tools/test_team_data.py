import json

from competition_tools.team.__main__ import main


def test_data_help_does_not_need_configuration(capsys):
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["data", "--help"])
    assert exc.value.code == 0
    assert "acquire" in capsys.readouterr().out


def test_plan_is_offline_and_reports_unverified_provider(tmp_path, capsys):
    config = tmp_path / "team.toml"
    config.write_text(
        f'schema_version="competition.team.v1"\ndata_root="{tmp_path.as_posix()}"\nenvironment_root="{tmp_path.as_posix()}/envs"\n'
    )
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "schema": "competition.dataset_spec.v1",
                "dataset_id": "us-study",
                "version": "v1",
                "source": "algoseek",
                "market": "US",
                "products": ["SPY"],
                "quote_currency": "USD",
                "start": "2016-01-01",
                "end": "2026-09-30",
                "timezone": "America/New_York",
                "calendar": "XNYS",
                "price_basis": "adjusted",
                "universe_status": "fixed_current",
                "budget": {"requests": 100, "bytes": 262144000, "seconds": 1800},
            }
        )
    )
    assert main(["data", "plan", "--config", str(config), "--spec", str(spec)]) == 2
    value = json.loads(capsys.readouterr().out)
    assert "PROVIDER_CONTRACT_UNVERIFIED" in value["issue_codes"]
    assert not (tmp_path / "2026-quant-competition/datasets").exists()


def test_concurrent_acquisition_cannot_modify_owned_version(tmp_path, monkeypatch):
    import pytest
    from competition_tools.team.config import TeamConfig
    from competition_tools.team.data import execute
    from competition_tools.datasets import acquisition

    def reject_network(*args):
        pytest.fail("An existing acquisition lock must prevent network access")

    monkeypatch.setattr(acquisition, "acquire", reject_network)
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "schema": "competition.dataset_spec.v1",
                "dataset_id": "spot",
                "version": "v1",
                "source": "binance_spot",
                "market": "crypto",
                "products": ["BTCUSDT"],
                "quote_currency": "USDT",
                "start": "2024-10-01",
                "end": "2024-12-31",
                "timezone": "UTC",
                "calendar": "365",
                "price_basis": "raw",
                "universe_status": "fixed_current",
                "budget": {"requests": 20, "bytes": 26214400, "seconds": 600},
            }
        )
    )
    parent = tmp_path / "2026-quant-competition/datasets/spot"
    parent.mkdir(parents=True)
    (parent / "v1.acquire-lock").write_text("another acquisition")
    with pytest.raises(ValueError, match="ACQUISITION_IN_PROGRESS"):
        execute("acquire", TeamConfig(tmp_path, tmp_path / "envs"), spec)
    assert not (parent / "v1.partial").exists()


def test_missing_spec_has_sanitized_machine_diagnostic(tmp_path, capsys):
    config = tmp_path / "team.toml"
    config.write_text(
        f'schema_version="competition.team.v1"\ndata_root="{tmp_path.as_posix()}"\nenvironment_root="{tmp_path.as_posix()}/envs"\n'
    )
    assert (
        main(
            [
                "data",
                "plan",
                "--config",
                str(config),
                "--spec",
                str(tmp_path / "private-name-missing.json"),
            ]
        )
        == 2
    )
    output = capsys.readouterr().out
    assert "private-name" not in output
    assert json.loads(output)["issue_codes"] == ["INVALID_CONFIGURATION"]
