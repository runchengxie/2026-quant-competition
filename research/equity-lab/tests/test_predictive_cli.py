from pathlib import Path
from types import SimpleNamespace

import pytest

from equity_lab.predictive.cli import main


@pytest.mark.parametrize("relative", ["private-result", "site/private-result"])
def test_private_outputs_anywhere_in_checkout_are_rejected(
    tmp_path, monkeypatch, capsys, relative
):
    source = tmp_path / "input" / "daily.parquet"
    source.parent.mkdir()
    source.write_bytes(b"not-read-by-supervisor")
    repository = Path(__file__).resolve().parents[3]
    monkeypatch.setattr(
        "subprocess.run", lambda *args, **kwargs: SimpleNamespace(returncode=0)
    )
    with pytest.raises(SystemExit) as error:
        main(
            [
                "--input",
                str(source),
                "--output",
                str(repository / relative),
                "--mode",
                "exploratory_source_candidates",
            ]
        )
    assert error.value.code == 2
    assert "outside the checkout" in capsys.readouterr().err


def test_external_destination_still_launches_bounded_worker(tmp_path, monkeypatch):
    source = tmp_path / "input" / "daily.parquet"
    source.parent.mkdir()
    source.write_bytes(b"not-read-by-supervisor")

    def bounded(command, *, timeout, env):
        assert timeout == 1200
        assert env["OMP_NUM_THREADS"] == "2"
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("subprocess.run", bounded)
    assert (
        main(
            [
                "--input",
                str(source),
                "--output",
                str(tmp_path / "result"),
                "--mode",
                "exploratory_source_candidates",
            ]
        )
        == 0
    )
