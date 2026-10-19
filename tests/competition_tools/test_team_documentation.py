"""Copyable localized commands and scoped licensing remain synchronized."""

from pathlib import Path
import re
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "document", ["operations/team-quickstart", "research/international-experiments"]
)
def test_localized_quickstarts_share_commands_and_valid_links(document):
    for locale in ("", ".zh-CN"):
        path = ROOT / f"docs/{document}{locale}.md"
        content = path.read_text(encoding="utf-8")
        commands = re.findall(r"```sh\n(.*?)```", content, re.S)
        if not locale:
            english = commands
        else:
            assert commands == english
        for target in re.findall(r"\]\(([^)]+)\)", content):
            if not target.startswith("https:"):
                assert (path.parent / target.split("#")[0]).is_file(), target


def test_scoped_license_is_included_in_root_wheel_configuration():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert (
        "LICENSE"
        in config["tool"]["setuptools"]["package-data"]["competition_tools.team"]
    )
