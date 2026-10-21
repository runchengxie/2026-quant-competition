import argparse
import json
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import re
from typing import Callable
from urllib.parse import unquote, urlsplit

PAGES_BASE_PATH = "/2026-quant-competition"

SENSITIVE = {
    "credential": re.compile(
        r"(?i)(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{30,}|"
        r"sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
    ),
    "credential_assignment": re.compile(
        r"(?i)(?:api[_-]?key|secret|token|password)[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9/_+=.-]{24,}"
    ),
    "account_or_order_identifier": re.compile(
        r"(?i)\b(?:account[_ -]?id|account[_ -]?number|order[_ -]?id)[\"']?\s*[:=]\s*[\"']?[A-Z0-9-]{5,}"
    ),
}

REQUIRED_SOURCE = {
    "astro.config.mjs",
    "package.json",
    "package-lock.json",
    "src/pages/index.astro",
    "src/pages/zh-CN/index.astro",
}
REQUIRED_OUTPUT = {"index.html", "zh-CN/index.html"}
IGNORED_SOURCE_DIRS = {"node_modules", ".astro", "dist"}
TEXT_SUFFIXES = {
    ".astro",
    ".css",
    ".html",
    ".js",
    ".json",
    ".mjs",
    ".svg",
    ".ts",
    ".txt",
}
PUBLIC_ASSET_SUFFIXES = {
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
    ".woff",
    ".woff2",
}
ASSET_SUFFIXES = PUBLIC_ASSET_SUFFIXES | {".css", ".js"}


class _PageMetadata(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.language: str | None = None
        self.hrefs: list[str] = []
        self.validation_facts: list[tuple[str, str | None, str | None]] = []
        self.expansion_facts: list[tuple[str, str | None]] = []
        self.study_facts: list[tuple[str, str | None]] = []
        self.dashboard_facts: list[str | None] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        if "data-dashboard-selected" in attributes:
            self.dashboard_facts.append(attributes.get("data-facts"))
        if study_id := attributes.get("data-study-id"):
            self.study_facts.append((study_id, attributes.get("data-facts")))
        if expansion_id := attributes.get("data-expansion-id"):
            self.expansion_facts.append((expansion_id, attributes.get("data-facts")))
        if result_id := attributes.get("data-result-id"):
            self.validation_facts.append(
                (
                    result_id,
                    attributes.get("data-metrics"),
                    attributes.get("data-evidence"),
                )
            )
        if tag == "html":
            self.language = attributes.get("lang")
        if tag in {"a", "link"} and attributes.get("href"):
            self.hrefs.append(attributes["href"])


def _allowed_source(relative_path: PurePosixPath) -> bool:
    path = relative_path.as_posix()
    if path in {
        "astro.config.mjs",
        "public/third-party-notices.txt",
        "package.json",
        "package-lock.json",
        "playwright.config.mjs",
        "tests/theme.spec.mjs",
        "tests/expansion.spec.mjs",
        "tests/study.spec.mjs",
        "tsconfig.json",
        "src/i18n/en.json",
        "src/i18n/zh-CN.json",
        "src/data/strategy-validation.json",
        "src/data/strategy-expansion.v1.json",
        "src/data/real-data-study.v1.json",
        "src/data/real-data-series.v1.json",
        "document-routes.mjs",
        "remark-doc-links.mjs",
        "src/lib/documents.ts",
        "src/scripts/dashboard-state.mjs",
        "src/scripts/performance-charts.mjs",
        "tests/dashboard-state.test.mjs",
        "tests/dashboard.spec.mjs",
        "tests/docs-links.test.mjs",
        "tests/docs.spec.mjs",
    }:
        return True
    if path.startswith("src/"):
        return relative_path.suffix in {".astro", ".css"}
    if path.startswith("public/"):
        return relative_path.suffix.lower() in PUBLIC_ASSET_SUFFIXES
    return False


def _allowed_output(relative_path: PurePosixPath) -> bool:
    return (
        relative_path.as_posix() == "third-party-notices.txt"
        or relative_path.suffix.lower() in ASSET_SUFFIXES | {".html"}
    )


def _collect_files(
    root: Path,
    label: str,
    allowed: Callable[[PurePosixPath], bool],
    errors: list[str],
    ignored_directories: set[str] | None = None,
) -> tuple[set[str], list[Path]]:
    ignored_directories = ignored_directories or set()
    if root.is_symlink() or not root.is_dir():
        errors.append(f"{label} directory is missing or is a symlink: {root}")
        return set(), []

    paths: set[str] = set()
    files: list[Path] = []
    for path in root.rglob("*"):
        relative_path = PurePosixPath(path.relative_to(root).as_posix())
        if relative_path.parts[0] in ignored_directories:
            continue
        relative_name = relative_path.as_posix()
        if path.is_symlink():
            errors.append(f"symlink in {label}: {relative_name}")
        elif path.is_dir():
            continue
        elif path.is_file():
            paths.add(relative_name)
            if not allowed(relative_path):
                errors.append(f"unrecognized {label} path: {relative_name}")
            else:
                files.append(path)
    return paths, files


def _scan_sensitive(files: list[Path], label: str, errors: list[str]) -> None:
    for path in files:
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            contents = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            errors.append(f"cannot read {label} file {path.name}: {error}")
            continue
        for name, pattern in SENSITIVE.items():
            if pattern.search(contents):
                errors.append(
                    f"sensitive pattern ({name}) detected in {label} file {path.name}"
                )


def _validate_localized_output(
    built_dir: Path, output_paths: set[str], errors: list[str]
) -> None:
    route_requirements = {
        "index.html": {
            "language": "en",
            "locale_switch": f"{PAGES_BASE_PATH}/zh-CN/",
        },
        "zh-CN/index.html": {
            "language": "zh-CN",
            "locale_switch": f"{PAGES_BASE_PATH}/",
        },
    }
    validation_facts: list[list[tuple[str, str | None, str | None]]] = []
    expansion_facts: list[list[tuple[str, str | None]]] = []
    study_facts: list[list[tuple[str, str | None]]] = []
    for relative_path, requirements in route_requirements.items():
        if relative_path not in output_paths:
            continue
        page_path = built_dir / Path(relative_path)
        try:
            page = page_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            errors.append(f"cannot read output page {relative_path}: {error}")
            continue

        metadata = _PageMetadata()
        metadata.feed(page)
        validation_facts.append(sorted(metadata.validation_facts))
        expansion_facts.append(sorted(metadata.expansion_facts))
        study_facts.append(sorted(metadata.study_facts))
        if metadata.language != requirements["language"]:
            errors.append(f"locale metadata mismatch in output page {relative_path}")
        if requirements["locale_switch"] not in metadata.hrefs:
            errors.append(f"locale switch path missing in output page {relative_path}")
        if not any(
            href.startswith(f"{PAGES_BASE_PATH}/_astro/") and href.endswith(".css")
            for href in metadata.hrefs
        ):
            errors.append(
                f"stylesheet missing repository base path in output page {relative_path}"
            )

    if len(validation_facts) == 2 and validation_facts[0] != validation_facts[1]:
        errors.append("validation facts differ between localized output pages")
    if len(expansion_facts) == 2 and expansion_facts[0] != expansion_facts[1]:
        errors.append("expansion facts differ between localized output pages")
    if len(study_facts) == 2 and study_facts[0] != study_facts[1]:
        errors.append("study facts differ between localized output pages")


def check_site(source_dir: Path, built_dir: Path) -> list[str]:
    errors: list[str] = []
    source_paths, source_files = _collect_files(
        source_dir,
        "source",
        _allowed_source,
        errors,
        ignored_directories=IGNORED_SOURCE_DIRS,
    )
    output_paths, output_files = _collect_files(
        built_dir,
        "output",
        _allowed_output,
        errors,
    )

    missing_source = REQUIRED_SOURCE - source_paths
    missing_output = REQUIRED_OUTPUT - output_paths
    if missing_source:
        errors.append(f"required source file missing: {sorted(missing_source)}")
    if missing_output:
        errors.append(f"required output file missing: {sorted(missing_output)}")

    _validate_localized_output(built_dir, output_paths, errors)
    snapshot = source_dir / "src/data/real-data-study.v1.json"
    if snapshot.is_file():
        from competition_tools.evaluation.study_publication import validate_public_study

        try:
            value = validate_public_study(
                json.loads(snapshot.read_text(encoding="utf-8"))
            )
            expected = {r["job_id"]: r for r in value["results"]}
            for relative in REQUIRED_OUTPUT & output_paths:
                metadata = _PageMetadata()
                metadata.feed((built_dir / relative).read_text(encoding="utf-8"))
                actual = {key: json.loads(facts) for key, facts in metadata.study_facts}
                if actual != expected or len(metadata.study_facts) != len(expected):
                    errors.append("study facts differ from reviewed source snapshot")
                for facts in metadata.dashboard_facts:
                    selected = json.loads(facts)
                    if selected != expected.get(selected.get("job_id")):
                        errors.append(
                            "dashboard facts differ from reviewed source snapshot"
                        )
                if (
                    source_dir / "src/components/PerformanceDashboard.astro"
                ).exists() and len(metadata.dashboard_facts) != 1:
                    errors.append("dashboard selected facts missing")
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            errors.append("invalid public study snapshot or output")
    series_path = source_dir / "src/data/real-data-series.v1.json"
    if series_path.is_file():
        from competition_tools.evaluation.study_series import validate_public_series

        try:
            validate_public_series(
                json.loads(series_path.read_text(encoding="utf-8")),
                json.loads(snapshot.read_text(encoding="utf-8")),
            )
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            errors.append("invalid public series snapshot")
    if "document-routes.mjs" in source_paths:
        _validate_documentation(built_dir, output_paths, errors)
    _scan_sensitive(source_files, "source", errors)
    _scan_sensitive(output_files, "output", errors)
    return errors


def _validate_documentation(
    built_dir: Path, output_paths: set[str], errors: list[str]
) -> None:
    expected = {
        f"{prefix}docs/{slug + '/' if slug else ''}index.html": (
            "zh-CN" if prefix else "en",
            f"{PAGES_BASE_PATH}/{'docs/' if prefix else 'zh-CN/docs/'}{slug + '/' if slug else ''}",
        )
        for prefix in ("", "zh-CN/")
        for slug in (
            "",
            "architecture",
            "quickstart",
            "datasets",
            "study",
            "strategies",
        )
    }
    for name in expected.keys() - output_paths:
        errors.append(f"documentation route missing: {name}")
    cache = {}

    def metadata(name):
        if name not in cache:
            page = _PageMetadata()
            page.feed((built_dir / name).read_text(encoding="utf-8"))
            cache[name] = page
        return cache[name]

    for name in output_paths:
        if (
            name.startswith(("docs/", "zh-CN/docs/"))
            and name.endswith(".html")
            and name not in expected
        ):
            errors.append(f"unreviewed documentation route: {name}")
    for name in expected.keys() & output_paths:
        try:
            page = metadata(name)
            language, switch = expected[name]
            if page.language != language or switch not in page.hrefs:
                errors.append(f"documentation locale or switch mismatch: {name}")
            for href in page.hrefs:
                parts = urlsplit(href)
                if parts.scheme or parts.netloc:
                    continue
                if parts.path.startswith(PAGES_BASE_PATH + "/"):
                    relative = unquote(parts.path[len(PAGES_BASE_PATH) + 1 :])
                    if ".." in PurePosixPath(relative).parts:
                        errors.append(f"invalid documentation link: {name}")
                        continue
                    target = (
                        relative + "index.html"
                        if not relative or relative.endswith("/")
                        else relative
                    )
                elif not parts.path:
                    target = name
                else:
                    errors.append(f"unresolved documentation link: {name}")
                    continue
                if target not in output_paths:
                    errors.append(
                        f"documentation link target missing: {name} -> {target}"
                    )
                elif (
                    parts.fragment
                    and target.endswith(".html")
                    and unquote(parts.fragment) not in metadata(target).ids
                ):
                    errors.append(
                        f"documentation link fragment missing: {name} -> {target}#{parts.fragment}"
                    )
        except (OSError, ValueError, TypeError):
            errors.append(f"invalid documentation output: {name}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check public Pages source and generated output"
    )
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--built-dir", required=True, type=Path)
    args = parser.parse_args()

    errors = check_site(args.source_dir, args.built_dir)
    if errors:
        print("\n".join(errors))
        return 1
    print(
        "Pages content check passed: allowlisted source and generated site; no sensitive patterns found."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
