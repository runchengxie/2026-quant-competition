import json
import html
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


def editorial_site_fixture(tmp_path):
    from competition_tools.check_pages_content import _expected_editorial_summary

    source, built = make_site_trees(tmp_path)
    data = Path(__file__).resolve().parents[2] / "site/src/data"
    values = {}
    for name in ("strategy-robustness", "strategy-readiness"):
        value = json.loads((data / f"{name}.v1.json").read_text())
        values[name] = value
        target = source / f"src/data/{name}.v1.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(value))
    component = source / "src/components/EditorialHome.astro"
    component.parent.mkdir()
    component.write_text("<!-- Editorial homepage -->")
    summary = _expected_editorial_summary(
        values["strategy-robustness"], values["strategy-readiness"]
    )
    for prefix in ("", "zh-CN/"):
        target = built / f"{prefix}strategies/index.html"
        target.parent.mkdir(parents=True)
        target.write_text(
            "".join(
                f'<section data-{attribute}-facts="{html.escape(json.dumps(values[name]), quote=True)}"></section>'
                for attribute, name in (
                    ("robustness", "strategy-robustness"),
                    ("readiness", "strategy-readiness"),
                )
            )
        )
        target = built / f"{prefix}index.html"
        target.write_text(
            target.read_text().replace(
                "</body>",
                f'<section data-editorial-facts="{html.escape(json.dumps(summary), quote=True)}"></section></body>',
            )
        )
    return source, built, summary


def test_editorial_summary_matches_reviewed_source(tmp_path):
    source, built, summary = editorial_site_fixture(tmp_path)
    assert summary["observation"]["observations"] == 0
    assert [g["returnWins"] for g in summary["us"]] == [4, 4, 4]
    assert summary["us"][1]["medianReturnChange"] == pytest.approx(
        -0.0197321676330644, abs=1e-12
    )
    assert [g["returnWins"] for g in summary["crypto"]] == [6, 5]
    assert check_site(source, built) == []


@pytest.mark.parametrize(
    "mutation", ["count", "median", "extra", "missing", "duplicate", "boolean"]
)
def test_editorial_summary_rejects_mutated_or_extra_fields(tmp_path, mutation):
    source, built, summary = editorial_site_fixture(tmp_path)
    target = built / "index.html"
    if mutation == "count":
        summary["coverage"]["requested_jobs"] = 113
    elif mutation == "median":
        summary["us"][0]["medianReturnChange"] = 0
    elif mutation == "extra":
        summary["private_path"] = "not-public"
    elif mutation == "boolean":
        summary["observation"]["observations"] = False
    original = target.read_text()
    section = f'<section data-editorial-facts="{html.escape(json.dumps(summary), quote=True)}"></section>'
    import re

    changed = re.sub(
        r'<section data-editorial-facts="[^"]+"></section>',
        ""
        if mutation == "missing"
        else section * (2 if mutation == "duplicate" else 1),
        original,
    )
    target.write_text(changed)
    assert any("editorial" in issue for issue in check_site(source, built))


def test_editorial_summary_requires_locale_equivalence(tmp_path):
    source, built, summary = editorial_site_fixture(tmp_path)
    summary["observation"]["observations"] = 1
    target = built / "zh-CN/index.html"
    import re

    target.write_text(
        re.sub(
            r'data-editorial-facts="[^"]+"',
            'data-editorial-facts="'
            + html.escape(json.dumps(summary), quote=True)
            + '"',
            target.read_text(),
        )
    )
    assert any("editorial" in issue for issue in check_site(source, built))


def test_editorial_numbers_preserve_json_number_semantics(tmp_path):
    source, built, _ = editorial_site_fixture(tmp_path)
    for relative in ("index.html", "zh-CN/index.html"):
        path = built / relative
        path.write_text(
            path.read_text().replace(
                "&quot;observations&quot;: 0", "&quot;observations&quot;: 0.0"
            )
        )
    assert check_site(source, built) == []


def test_robustness_snapshot_requires_exact_bilingual_facts(tmp_path):
    source, built = make_site_trees(tmp_path)
    canonical = (
        Path(__file__).resolve().parents[2]
        / "site/src/data/strategy-robustness.v1.json"
    )
    value = json.loads(canonical.read_text())
    path = source / "src/data/strategy-robustness.v1.json"
    path.parent.mkdir()
    path.write_text(json.dumps(value))
    for relative in ("strategies/index.html", "zh-CN/strategies/index.html"):
        target = built / relative
        target.parent.mkdir(parents=True)
        target.write_text(
            '<section data-robustness-facts="'
            + html.escape(json.dumps(value), quote=True)
            + '"></section>'
        )
    assert check_site(source, built) == []
    (built / "zh-CN/strategies/index.html").write_text(
        '<section data-robustness-facts="{}"></section>'
    )
    assert any("robustness facts" in issue for issue in check_site(source, built))


def test_dex_readiness_requires_exact_bilingual_output(tmp_path):
    source, built = make_site_trees(tmp_path)
    canonical = (
        Path(__file__).resolve().parents[2]
        / "site/src/data/dex-factor-readiness.v1.json"
    )
    value = json.loads(canonical.read_text())
    path = source / "src/data/dex-factor-readiness.v1.json"
    path.parent.mkdir()
    path.write_text(json.dumps(value))
    for relative in ["factors/index.html", "zh-CN/factors/index.html"]:
        target = built / relative
        target.parent.mkdir(parents=True)
        target.write_text(
            '<section data-dex-facts="'
            + html.escape(json.dumps(value), quote=True)
            + '"></section>'
        )
    assert check_site(source, built) == []
    (built / "zh-CN/factors/index.html").write_text(
        '<section data-dex-facts="{}"></section>'
    )
    assert any("DEX readiness facts" in issue for issue in check_site(source, built))


def controls_site_fixture(tmp_path, *, measured=False):
    from test_controls_publication import measured_fixture

    source, built = make_site_trees(tmp_path)
    value = measured_fixture()
    if not measured:
        value.update(
            status="readiness_only",
            results=[],
            pairs=[],
            blockers=["PUBLICATION_PERMISSION_UNVERIFIED", "INCOMPLETE_CONTROLS_RUN"],
            coverage=dict(requested_jobs=2, completed_jobs=1, blocked_jobs=1),
        )
    path = source / "src/data/strategy-controls.v1.json"
    path.parent.mkdir()
    path.write_text(json.dumps(value))
    for relative in ("strategies/index.html", "zh-CN/strategies/index.html"):
        target = built / relative
        target.parent.mkdir(parents=True)
        target.write_text(
            '<section data-controls-facts="'
            + html.escape(json.dumps(value), quote=True)
            + '"></section>'
        )
    return source, built


def test_controls_completion_and_failed_denominator_match_both_languages(tmp_path):
    source, built = controls_site_fixture(tmp_path)
    assert check_site(source, built) == []
    (built / "zh-CN/strategies/index.html").write_text(
        '<section data-controls-facts="{}"></section>'
    )
    assert any("controls facts" in issue for issue in check_site(source, built))


def test_controls_measured_snapshot_requires_a_source_controlled_review(tmp_path):
    source, built = controls_site_fixture(tmp_path, measured=True)
    assert any(
        "unreviewed measured controls" in issue for issue in check_site(source, built)
    )


def test_allows_reviewed_expansion_snapshot_but_still_scans_secrets(tmp_path):
    source, built = make_site_trees(tmp_path)
    path = source / "src/data/strategy-expansion.v1.json"
    path.parent.mkdir()
    path.write_text('{"schema": "competition.public_strategy_expansion.v1"}')
    test = source / "tests/expansion.spec.mjs"
    test.parent.mkdir()
    test.write_text("// Reviewed bilingual presentation regression test")
    assert check_site(source, built) == []
    path.write_text(json.dumps({"api_key": "sensitive-example-value-1234567890"}))
    assert any("sensitive pattern" in error for error in check_site(source, built))


def test_strategy_readiness_has_exact_public_status_in_both_languages(tmp_path):
    from test_public_research_readiness import public_fixture

    source, built = controls_site_fixture(tmp_path)
    value = public_fixture()
    (source / "src/data/strategy-readiness.v1.json").write_text(json.dumps(value))
    for relative in ("strategies/index.html", "zh-CN/strategies/index.html"):
        target = built / relative
        target.write_text(
            target.read_text()
            + '<aside data-readiness-facts="'
            + html.escape(json.dumps(value), quote=True)
            + '"></aside>'
        )
    assert check_site(source, built) == []
    target.write_text(
        target.read_text().replace("data-readiness-facts=", "data-ignored-facts=")
    )
    assert any(
        "strategy readiness facts" in issue for issue in check_site(source, built)
    )


def test_expansion_facts_must_match_between_locales(tmp_path):
    source, built = make_site_trees(tmp_path)
    for relative, value in (("index.html", "1"), ("zh-CN/index.html", "2")):
        path = built / relative
        path.write_text(
            path.read_text(encoding="utf-8")
            + f'<tr data-expansion-id="daily-0" data-facts="{value}"></tr>',
            encoding="utf-8",
        )
    assert any("expansion facts differ" in error for error in check_site(source, built))


def test_study_facts_must_match_between_locales(tmp_path):
    source, built = make_site_trees(tmp_path)
    for relative, value in (("index.html", "1"), ("zh-CN/index.html", "2")):
        path = built / relative
        path.write_text(
            path.read_text(encoding="utf-8")
            + f'<tr data-study-id="example" data-facts="{value}"></tr>',
            encoding="utf-8",
        )
    assert any("study facts differ" in error for error in check_site(source, built))


def test_study_snapshot_requires_strict_public_contract(tmp_path):
    source, built = make_site_trees(tmp_path)
    path = source / "src/data/real-data-study.v1.json"
    path.parent.mkdir()
    path.write_text(
        '{"schema":"competition.public_study.v1","private_path":"C:/private"}'
    )
    assert any("invalid public study" in error for error in check_site(source, built))


def test_portfolio_series_gate_rejects_nested_private_metadata(tmp_path):
    source, built = make_site_trees(tmp_path)
    original = Path(__file__).resolve().parents[2] / "site/src/data"
    study = json.loads(
        (original / "real-data-study.v1.json").read_text(encoding="utf-8")
    )
    series = json.loads(
        (original / "real-data-series.v1.json").read_text(encoding="utf-8")
    )
    series["series"][0]["points"][0]["private_location"] = "C:/private/raw.csv"
    target = source / "src/data"
    target.mkdir()
    (target / "real-data-study.v1.json").write_text(json.dumps(study), encoding="utf-8")
    (target / "real-data-series.v1.json").write_text(
        json.dumps(series), encoding="utf-8"
    )
    assert any("invalid public series" in error for error in check_site(source, built))


def test_documentation_registry_requires_all_reviewed_routes(tmp_path):
    source, built = make_site_trees(tmp_path)
    (source / "document-routes.mjs").write_text("export const documentRoutes=[];")
    assert any(
        "documentation route missing" in error for error in check_site(source, built)
    )


def test_documentation_routes_validate_locale_links_and_reject_unlisted_pages(tmp_path):
    source, built = make_site_trees(tmp_path)
    (source / "document-routes.mjs").write_text("// Reviewed document registry")
    for prefix in ("", "zh-CN/"):
        for slug in (
            "",
            "architecture",
            "quickstart",
            "datasets",
            "study",
            "strategies",
            "strategy-controls",
            "execution-evidence",
            "observation-registry",
            "strategy-robustness",
            "data-refresh",
            "native-process-diagnostics",
            "equity-predictive",
        ):
            suffix = f"docs/{slug + '/' if slug else ''}"
            p = built / prefix / suffix / "index.html"
            p.parent.mkdir(parents=True, exist_ok=True)
            language = "zh-CN" if prefix else "en"
            switch = BASE_PATH + "/" + ("" if prefix else "zh-CN/") + suffix
            p.write_text(rendered_page(language, switch), encoding="utf-8")
    assert check_site(source, built) == []
    extra = built / "docs/internal/index.html"
    extra.parent.mkdir()
    extra.write_text(rendered_page("en", BASE_PATH + "/zh-CN/"))
    assert any(
        "unreviewed documentation route" in error for error in check_site(source, built)
    )


def test_documentation_fragment_must_exist(tmp_path):
    source, built = make_site_trees(tmp_path)
    (source / "document-routes.mjs").write_text("// Reviewed document registry")
    path = built / "docs/study/index.html"
    path.parent.mkdir(parents=True)
    path.write_text(
        rendered_page("en", BASE_PATH + "/zh-CN/docs/study/")
        + '<a href="#missing">Missing</a>'
    )
    assert any(
        "documentation link fragment missing" in error
        for error in check_site(source, built)
    )


def test_study_gate_rejects_nested_private_products(tmp_path):
    import html

    source, built = make_site_trees(tmp_path)
    value = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "site/src/data/real-data-study.v1.json"
        ).read_text(encoding="utf-8")
    )
    product = value["results"][0]["products"][0]
    value["results"][0]["products"] = {
        product: {"private_location": "C:/private/raw.csv", "note": "PRIVATE_SENTINEL"}
    }
    path = source / "src/data/real-data-study.v1.json"
    path.parent.mkdir()
    path.write_text(json.dumps(value), encoding="utf-8")
    rows = "".join(
        f'<tr data-study-id="{r["job_id"]}" data-facts="{html.escape(json.dumps(r), quote=True)}"></tr>'
        for r in value["results"]
    )
    for relative in ("index.html", "zh-CN/index.html"):
        p = built / relative
        p.write_text(p.read_text(encoding="utf-8") + rows, encoding="utf-8")
    assert any("invalid public study" in error for error in check_site(source, built))


def test_allows_only_reviewed_validation_snapshot_and_scans_its_content(tmp_path):
    source, built = make_site_trees(tmp_path)
    data = source / "src/data"
    data.mkdir()
    snapshot = data / "strategy-validation.json"
    snapshot.write_text('{"schema_version": 1}', encoding="utf-8")
    assert check_site(source, built) == []
    snapshot.write_text(
        json.dumps({"api_key": "synthetic-private-value-1234567890"}), encoding="utf-8"
    )
    assert any("credential_assignment" in error for error in check_site(source, built))
    snapshot.write_text('{"schema_version": 1}', encoding="utf-8")
    (data / "raw-response.json").write_text("{}", encoding="utf-8")
    assert any(
        "unrecognized source path" in error for error in check_site(source, built)
    )


def test_rejects_unrecognized_source_file(tmp_path):
    source, built = make_site_trees(tmp_path)
    (source / "src/pages/unreviewed.ts").write_text("export {};", encoding="utf-8")

    errors = check_site(source, built)

    assert any("unrecognized source path" in error for error in errors)


def test_allows_reviewed_browser_tests_but_still_scans_them(tmp_path):
    source, built = make_site_trees(tmp_path)
    (source / "tests").mkdir()
    browser_test = source / "tests/theme.spec.mjs"
    browser_test.write_text("export {};", encoding="utf-8")
    (source / "playwright.config.mjs").write_text("export {};", encoding="utf-8")
    assert check_site(source, built) == []
    browser_test.write_text(
        'const api_key = "synthetic-private-value-1234567890";', encoding="utf-8"
    )
    assert any("credential_assignment" in error for error in check_site(source, built))


def test_allows_reviewed_locale_catalogs_but_rejects_other_json(tmp_path):
    source, built = make_site_trees(tmp_path)
    catalogs = source / "src/i18n"
    catalogs.mkdir()
    for name in ("en.json", "zh-CN.json"):
        (catalogs / name).write_text('{"demo": "Synthetic example"}', encoding="utf-8")
    assert check_site(source, built) == []

    (catalogs / "account.json").write_text("{}", encoding="utf-8")
    assert any(
        "unrecognized source path" in error for error in check_site(source, built)
    )


def test_scans_locale_catalog_for_secrets(tmp_path):
    source, built = make_site_trees(tmp_path)
    catalogs = source / "src/i18n"
    catalogs.mkdir()
    (catalogs / "en.json").write_text(
        '{"api_key": "abcdefghijklmnopqrstuvwxyz"}', encoding="utf-8"
    )
    assert any("sensitive pattern" in error for error in check_site(source, built))


@pytest.mark.parametrize("key", ["account_id", "account_number", "order_id"])
def test_rejects_quoted_json_account_and_order_identifiers(tmp_path, key):
    source, built = make_site_trees(tmp_path)
    catalogs = source / "src/i18n"
    catalogs.mkdir()
    (catalogs / "en.json").write_text(
        json.dumps({key: "EXAMPLE00001"}), encoding="utf-8"
    )
    assert any(
        "account_or_order_identifier" in error for error in check_site(source, built)
    )


def test_does_not_ignore_nested_directory_named_dist(tmp_path):
    source, built = make_site_trees(tmp_path)
    private_source = source / "src/components/dist/private.astro"
    private_source.parent.mkdir(parents=True)
    private_source.write_text(
        'api_key = "abcdefghijklmnopqrstuvwxyz"', encoding="utf-8"
    )

    errors = check_site(source, built)

    assert any("sensitive pattern" in error for error in errors)


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


@pytest.mark.parametrize("translated_return", ["0.1", "0.2"])
def test_locales_preserve_validation_machine_facts(tmp_path, translated_return):
    source, built = make_site_trees(tmp_path)
    for path, value in (
        (built / "index.html", "0.1"),
        (built / "zh-CN/index.html", translated_return),
    ):
        html = path.read_text(encoding="utf-8")
        row = f'<tr data-result-id="US-sma" data-metrics="{value}" data-evidence="limited_universe"></tr>'
        path.write_text(html.replace("</body>", row + "</body>"), encoding="utf-8")
    errors = check_site(source, built)
    assert any("validation facts differ" in error for error in errors) == (
        translated_return != "0.1"
    )


def test_notice_is_exactly_allowlisted_and_still_scanned(tmp_path):
    source, built = make_site_trees(tmp_path)
    notice = source / "public/third-party-notices.txt"
    output = built / "third-party-notices.txt"
    notice.write_text("Third-party licenses", encoding="utf-8")
    output.write_text(notice.read_text(), encoding="utf-8")
    assert check_site(source, built) == []
    (source / "public/private.txt").write_text("not public")
    assert any("unrecognized source path" in e for e in check_site(source, built))
    notice.write_text('api_key = "sensitive-example-value-1234567890"')
    assert any("sensitive pattern" in e for e in check_site(source, built))


@pytest.mark.parametrize("multipage", [False, True])
def test_ablation_facts_have_separate_strict_source_and_locale_parity(
    tmp_path, multipage
):
    import html
    from test_ablation_publication import public_fixture

    source, built = make_site_trees(tmp_path)
    value = public_fixture()
    p = source / "src/data/ablation-study.v1.json"
    p.parent.mkdir()
    p.write_text(json.dumps(value))
    if multipage:
        (source / "src/pages/strategies.astro").write_text("<!-- Strategy results -->")
        for prefix, locale, other in [("", "en", "zh-CN/"), ("zh-CN/", "zh-CN", "")]:
            for route in ["strategies/", "factors/", "docs/project/"]:
                page = built / f"{prefix}{route}index.html"
                page.parent.mkdir(parents=True, exist_ok=True)
                page.write_text(rendered_page(locale, f"{BASE_PATH}/{other}{route}"))
    routes = (
        ["strategies/index.html", "zh-CN/strategies/index.html"]
        if multipage
        else ["index.html", "zh-CN/index.html"]
    )
    for relative in routes:
        path = built / relative
        path.write_text(
            path.read_text()
            + "".join(
                '<tr data-ablation-id="'
                + r["job_id"]
                + '" data-facts="'
                + html.escape(json.dumps(r), quote=True)
                + '"></tr>'
                for r in value["results"]
            )
        )
    assert check_site(source, built) == []
    p = built / routes[1]
    p.write_text(p.read_text().replace("retrospective_ablation", "forward_validated"))
    assert any("ablation facts differ" in e for e in check_site(source, built))
