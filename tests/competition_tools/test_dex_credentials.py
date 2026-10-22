import json

import pytest

from competition_tools.datasets import dex_credentials as credentials


def setup(tmp_path):
    code, config = tmp_path / "code", tmp_path / "private"
    source = code / "2026-quant-competition/.env"
    source.parent.mkdir(parents=True)
    (source.parent / ".git").mkdir()
    source.write_bytes(
        b"OTHER=value\r\nDEXPAPRIKA_API_KEY='fixture-only'\r\n# retain\n"
    )
    workspace = tmp_path / "workspace.toml"
    workspace.write_text(
        f'code_root = "{code.as_posix()}"\nconfig_root = "{config.as_posix()}"\ndata_root = "{(tmp_path / "data").as_posix()}"\n'
    )
    return (
        source,
        config / "projects/2026-quant-competition/providers/dexpaprika.env",
        workspace,
    )


def test_migration_preserves_unrelated_bytes_and_recovers(tmp_path, capsys):
    source, destination, workspace = setup(tmp_path)
    result = credentials.migrate_key(source, destination, workspace)
    assert result == {"status": "migrated"}
    assert source.read_bytes() == b"OTHER=value\r\n# retain\n"
    assert credentials.load_key(destination) == "fixture-only"
    assert "fixture-only" not in json.dumps(result) + str(capsys.readouterr())
    assert credentials.migrate_key(source, destination, workspace) == {
        "status": "already_migrated"
    }
    assert list(destination.parent.glob(".dexpaprika-recovery-*"))


def test_duplicate_key_is_not_silently_selected(tmp_path):
    path = tmp_path / "provider.env"
    path.write_text("DEXPAPRIKA_API_KEY=first\nDEXPAPRIKA_API_KEY=second\n")
    with pytest.raises(ValueError, match="DUPLICATE_CREDENTIAL"):
        credentials.load_key(path)


@pytest.mark.parametrize(
    "value", ["", "${OTHER}", '"line\\nvalue"', "abc # comment", "'unfinished"]
)
def test_unsupported_values_are_rejected_without_echo(tmp_path, value):
    path = tmp_path / "provider.env"
    path.write_text("DEXPAPRIKA_API_KEY=" + value)
    with pytest.raises(ValueError, match="INVALID_CREDENTIAL"):
        credentials.load_key(path)


def test_conflict_keeps_source_and_destination(tmp_path):
    source, destination, workspace = setup(tmp_path)
    destination.parent.mkdir(parents=True)
    destination.write_text("DEXPAPRIKA_API_KEY=different\n")
    before = source.read_bytes()
    with pytest.raises(ValueError, match="CREDENTIAL_CONFLICT"):
        credentials.migrate_key(source, destination, workspace)
    assert source.read_bytes() == before
    assert "different" in destination.read_text()


def test_failure_before_source_replacement_keeps_recovery(tmp_path, monkeypatch):
    source, destination, workspace = setup(tmp_path)
    before = source.read_bytes()

    def fail(*args):
        raise OSError("synthetic interruption")

    monkeypatch.setattr(credentials, "_replace_source", fail)
    with pytest.raises(ValueError, match="MIGRATION_INTERRUPTED"):
        credentials.migrate_key(source, destination, workspace)
    assert source.read_bytes() == before
    assert credentials.load_key(destination) == "fixture-only"
    assert list(destination.parent.glob(".dexpaprika-recovery-*"))


def test_wrong_source_and_repository_destination_are_rejected(tmp_path):
    source, destination, workspace = setup(tmp_path)
    with pytest.raises(ValueError):
        credentials.migrate_key(source, source.parent / "provider.env", workspace)
    with pytest.raises(ValueError):
        credentials.migrate_key(source.parent / "other.env", destination, workspace)


def test_shared_config_root_cannot_be_used_as_provider_destination(tmp_path):
    source, destination, workspace = setup(tmp_path)
    shared = destination.parents[3] / "shared.env"
    before = source.read_bytes()
    with pytest.raises(ValueError, match="INVALID_MIGRATION_PATH"):
        credentials.migrate_key(source, shared, workspace)
    assert source.read_bytes() == before


def test_utf8_bom_assignment_preserves_other_content(tmp_path):
    source, destination, workspace = setup(tmp_path)
    source.write_bytes(
        b"\xef\xbb\xbfDEXPAPRIKA_API_KEY=fixture-only\r\nOTHER=value\r\n"
    )
    assert (
        credentials.migrate_key(source, destination, workspace)["status"] == "migrated"
    )
    assert source.read_bytes() == b"\xef\xbb\xbfOTHER=value\r\n"


def test_reparse_credential_paths_are_rejected(tmp_path):
    target = tmp_path / "real.env"
    target.write_text("DEXPAPRIKA_API_KEY=fixture-only")
    link = tmp_path / "link.env"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symlink creation privilege unavailable")
    with pytest.raises(ValueError):
        credentials.load_key(link)
