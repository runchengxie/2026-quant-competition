"""Interpreter selection must retain POSIX virtual-environment identity."""

import pytest

from competition_tools import check_holding_delivery as delivery


def test_symlinked_interpreter_preserves_environment_path(tmp_path, monkeypatch):
    base = tmp_path / "base-python"
    base.write_text("synthetic interpreter target")
    leaf = tmp_path / "venv/bin/python"
    leaf.parent.mkdir(parents=True)
    leaf.symlink_to(base)

    def reached_child(argv, **kwargs):
        assert argv[0] == str(leaf)
        raise RuntimeError("REACHED_SELECTED_INTERPRETER")

    monkeypatch.setattr(delivery, "run_child", reached_child)
    with pytest.raises(RuntimeError, match="REACHED_SELECTED_INTERPRETER"):
        delivery.main(
            ["--leaf-python", str(leaf), "--output-root", str(tmp_path / "out")]
        )


def test_extended_synthetic_contract_forwards_explicit_profile(tmp_path, monkeypatch):
    leaf = tmp_path / "python"
    leaf.write_text("synthetic interpreter")

    def reached_child(argv, **kwargs):
        assert argv[-1] == "--validation60"
        raise RuntimeError("REACHED_EXTENDED_PRODUCER")

    monkeypatch.setattr(delivery, "run_child", reached_child)
    with pytest.raises(RuntimeError, match="REACHED_EXTENDED_PRODUCER"):
        delivery.main(
            [
                "--leaf-python",
                str(leaf),
                "--output-root",
                str(tmp_path / "out"),
                "--validation60",
            ]
        )
