"""Retained source must survive removal of its original checkout."""

import subprocess
import pytest
from competition_tools.evaluation.ablation_source import (
    snapshot_source,
    verify_source_snapshot,
)


def fixture_repo(root):
    root.mkdir()
    for d in ["src", "research/equity-lab/src", "research/crypto-mm/src"]:
        (root / d).mkdir(parents=True)
        (root / d / "example.py").write_text("VALUE=1\n")
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-m",
            "fixture",
        ],
        check=True,
        capture_output=True,
    )
    return root


def test_snapshot_survives_original_checkout_removal_and_detects_mutation(tmp_path):
    root = fixture_repo(tmp_path / "repo")
    receipt = snapshot_source(root, tmp_path / "retained")
    root.rename(tmp_path / "moved-original")
    assert verify_source_snapshot(receipt) == receipt
    target = tmp_path / "retained/source/src/example.py"
    target.write_text("VALUE=2")
    with pytest.raises(ValueError):
        verify_source_snapshot(receipt)


def test_dirty_and_untracked_source_are_rejected(tmp_path):
    root = fixture_repo(tmp_path / "repo")
    (root / "src/example.py").write_text("VALUE=2")
    with pytest.raises(ValueError, match="DIRTY"):
        snapshot_source(root, tmp_path / "out")


def test_untracked_python_is_not_silently_archived(tmp_path):
    root = fixture_repo(tmp_path / "repo")
    (root / "src/extra.py").write_text("SECRET=1")
    with pytest.raises(ValueError, match="DIRTY"):
        snapshot_source(root, tmp_path / "out")


@pytest.mark.parametrize(
    "name", ["../escape.py", "/escape.py", "C:/escape.py", "folder\\escape.py"]
)
def test_unsafe_archive_members_are_rejected(tmp_path, monkeypatch, name):
    import io
    import zipfile
    from competition_tools.evaluation import ablation_source

    root = fixture_repo(tmp_path / "repo")
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as z:
        z.writestr(name, "value")
    # Windows ZipInfo normalizes backslashes while writing; patch both ZIP headers.
    raw = payload.getvalue()
    if chr(92) in name:
        raw = raw.replace(name.replace(chr(92), "/").encode(), name.encode())
    original = ablation_source._git

    def git(root, *args):
        return raw if args[0] == "archive" else original(root, *args)

    monkeypatch.setattr(ablation_source, "_git", git)
    with pytest.raises(ValueError, match="UNSAFE"):
        snapshot_source(root, tmp_path / "out")
