from pathlib import Path

import pytest

from competition_tools.check_pages_content import check_site

BASE_PATH = "/2026-quant-competition"


def rendered_page(locale: str, language_url: str, css_url: str | None = None) -> str:
    stylesheet = css_url or f"{BASE_PATH}/_astro/site.css"
    return (
        f'<html lang="{locale}"><head><link rel="stylesheet" href="{stylesheet}"></head>'
        f'<body><a href="{language_url}">Language</a></body></html>'
    )


def make_site_trees(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "site"
    built = tmp_path / "dist"
    source_files = {
        "astro.config.mjs": "export default {};",
        "package.json": '{"private": true}',
        "package-lock.json": '{"lockfileVersion": 3}',
        "src/pages/index.astro": '<html lang="en">English</html>',
        "src/pages/zh-CN/index.astro": '<html lang="zh-CN">简体中文</html>',
        "src/styles/global.css": "body { color: black; }",
        "public/project.svg": '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
    }
    for relative_path, contents in source_files.items():
        path = source / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    built_files = {
        "index.html": rendered_page("en", f"{BASE_PATH}/zh-CN/"),
        "zh-CN/index.html": rendered_page("zh-CN", f"{BASE_PATH}/"),
        "_astro/site.css": "body { color: black; }",
    }
    for relative_path, contents in built_files.items():
        path = built / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    return source, built


def test_allows_bilingual_astro_sources_assets_and_build_output(tmp_path):
    source, built = make_site_trees(tmp_path)
    (source / "node_modules").mkdir()
    (source / ".astro").mkdir()
    (source / "dist").mkdir()

    assert check_site(source, built) == []


def test_rejects_unrecognized_source_file(tmp_path):
    source, built = make_site_trees(tmp_path)
    (source / "src/pages/unreviewed.ts").write_text("export {};", encoding="utf-8")

    errors = check_site(source, built)

    assert any("unrecognized source path" in error for error in errors)


def test_rejects_public_javascript_source(tmp_path):
    source, built = make_site_trees(tmp_path)
    (source / "public/tracker.js").write_text("fetch('/api');", encoding="utf-8")

    errors = check_site(source, built)

    assert any("unrecognized source path" in error for error in errors)


def test_rejects_unrecognized_generated_file(tmp_path):
    source, built = make_site_trees(tmp_path)
    (built / "account.csv").write_text("private", encoding="utf-8")

    errors = check_site(source, built)

    assert any("unrecognized output path" in error for error in errors)


@pytest.mark.parametrize(
    ("tree", "relative_path", "contents", "expected_label"),
    [
        (
            "source",
            "src/pages/index.astro",
            'api_key = "abcdefghijklmnopqrstuvwxyz"',
            "credential",
        ),
        (
            "built",
            "zh-CN/index.html",
            "account_id=ACCNT00001",
            "account_or_order_identifier",
        ),
    ],
)
def test_scans_source_and_generated_files_for_sensitive_values(
    tmp_path, tree, relative_path, contents, expected_label
):
    source, built = make_site_trees(tmp_path)
    target = source if tree == "source" else built
    path = target / relative_path
    path.write_text(contents, encoding="utf-8")

    errors = check_site(source, built)

    assert any(expected_label in error for error in errors)


def test_rejects_missing_simplified_chinese_output_route(tmp_path):
    source, built = make_site_trees(tmp_path)
    (built / "zh-CN/index.html").unlink()

    errors = check_site(source, built)

    assert any("required output file missing" in error for error in errors)


def test_rejects_incorrect_simplified_chinese_language_metadata(tmp_path):
    source, built = make_site_trees(tmp_path)
    (built / "zh-CN/index.html").write_text(
        rendered_page("en", f"{BASE_PATH}/"), encoding="utf-8"
    )

    errors = check_site(source, built)

    assert any("locale metadata mismatch" in error for error in errors)


def test_rejects_missing_language_switch_destination(tmp_path):
    source, built = make_site_trees(tmp_path)
    (built / "index.html").write_text(rendered_page("en", "/zh-CN/"), encoding="utf-8")

    errors = check_site(source, built)

    assert any("locale switch path missing" in error for error in errors)


def test_rejects_stylesheet_without_github_pages_base_path(tmp_path):
    source, built = make_site_trees(tmp_path)
    (built / "index.html").write_text(
        rendered_page("en", f"{BASE_PATH}/zh-CN/", "/_astro/site.css"),
        encoding="utf-8",
    )

    errors = check_site(source, built)

    assert any("stylesheet missing repository base path" in error for error in errors)


@pytest.mark.parametrize("tree", ["source", "built"])
def test_rejects_symlinks_in_source_or_output(tmp_path, tree):
    source, built = make_site_trees(tmp_path)
    target = source if tree == "source" else built
    link = target / "linked.txt"
    try:
        link.symlink_to(target / "package.json")
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this platform")

    errors = check_site(source, built)

    assert any("symlink" in error for error in errors)
