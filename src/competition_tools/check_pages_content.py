import argparse
import json
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import re
from statistics import median
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
        self.ablation_facts: list[tuple[str, str | None]] = []
        self.study_facts: list[tuple[str, str | None]] = []
        self.dashboard_facts: list[str | None] = []
        self.dex_facts: list[str | None] = []
        self.controls_facts: list[str | None] = []
        self.robustness_facts: list[str | None] = []
        self.readiness_facts: list[str | None] = []
        self.editorial_facts: list[str | None] = []
        self.predictive_facts: list[str | None] = []
        self.incremental_facts: list[str | None] = []
        self.comparison_facts: list[str | None] = []
        self.low_turnover_facts: list[tuple[str | None, str | None, str | None]] = []
        self.progress_facts: list[str | None] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if "data-progress-facts" in attributes:
            self.progress_facts.append(attributes.get("data-progress-facts"))
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        if "data-dashboard-selected" in attributes:
            self.dashboard_facts.append(attributes.get("data-facts"))
        if "data-dex-facts" in attributes:
            self.dex_facts.append(attributes.get("data-dex-facts"))
        if "data-controls-facts" in attributes:
            self.controls_facts.append(attributes.get("data-controls-facts"))
        if "data-robustness-facts" in attributes:
            self.robustness_facts.append(attributes.get("data-robustness-facts"))
        if "data-readiness-facts" in attributes:
            self.readiness_facts.append(attributes.get("data-readiness-facts"))
        if "data-editorial-facts" in attributes:
            self.editorial_facts.append(attributes.get("data-editorial-facts"))
        if "data-predictive-facts" in attributes:
            self.predictive_facts.append(attributes.get("data-predictive-facts"))
        if "data-incremental-facts" in attributes:
            self.incremental_facts.append(attributes.get("data-incremental-facts"))
        if "data-comparison-facts" in attributes:
            self.comparison_facts.append(attributes.get("data-comparison-facts"))
        if "data-lt-facts" in attributes:
            self.low_turnover_facts.append(
                (
                    attributes.get("data-lt-market"),
                    attributes.get("data-lt-view"),
                    attributes.get("data-lt-facts"),
                )
            )
        if ablation_id := attributes.get("data-ablation-id"):
            self.ablation_facts.append((ablation_id, attributes.get("data-facts")))
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
        "src/data/ablation-study.v1.json",
        "src/lib/ablation.ts",
        "src/scripts/ablation-state.mjs",
        "src/scripts/ablation-charts.mjs",
        "tests/ablation-state.test.mjs",
        "tests/ablation.spec.mjs",
        "src/data/real-data-series.v1.json",
        "src/data/dex-factor-readiness.v1.json",
        "src/data/strategy-controls.v1.json",
        "src/data/strategy-robustness.v1.json",
        "src/scripts/robustness-state.mjs",
        "src/scripts/robustness-charts.mjs",
        "tests/robustness-state.test.mjs",
        "tests/robustness.spec.mjs",
        "src/scripts/editorial-summary.mjs",
        "tests/editorial-summary.test.mjs",
        "tests/editorial.spec.mjs",
        "tests/market-topics.spec.mjs",
        "tests/cnn-topic.spec.mjs",
        "tests/clear-home.spec.mjs",
        "tests/visual-refinement.spec.mjs",
        "src/i18n/home-en.json",
        "src/i18n/home-zh-CN.json",
        "src/i18n/cnn-topic-en.json",
        "src/i18n/cnn-topic-zh-CN.json",
        "src/data/cnn-archive-curves.v1.json",
        "src/data/crypto-cnn-research.v1.json",
        "src/data/crypto-cnn-followup.v1.json",
        "src/i18n/crypto-cnn-en.json",
        "src/i18n/crypto-cnn-zh-CN.json",
        "src/data/us-cnn-summary.v1.json",
        "src/data/us-cnn-ranges.v1.json",
        "src/i18n/us-cnn-en.json",
        "src/i18n/us-cnn-zh-CN.json",
        "src/lib/us-cnn-summary.mjs",
        "tests/us-cnn.spec.mjs",
        "tests/us-cnn-summary.test.mjs",
        "src/scripts/cnn-topic-chart.mjs",
        "src/i18n/market-topics-en.json",
        "src/i18n/market-topics-zh-CN.json",
        "src/data/strategy-readiness.v1.json",
        "src/data/equity-predictive.v1.json",
        "src/data/incremental-research.v1.json",
        "src/data/strategy-comparison.v1.json",
        "src/data/low-turnover.v1.json",
        "src/data/evidence-followup.v1.json",
        "src/i18n/followup-en.json",
        "src/i18n/followup-zh-CN.json",
        "src/scripts/chart-axis.mjs",
        "src/scripts/low-turnover-state.mjs",
        "src/scripts/low-turnover-charts.mjs",
        "src/scripts/market-panels.mjs",
        "src/i18n/low-turnover-en.json",
        "src/i18n/low-turnover-zh-CN.json",
        "tests/low-turnover.test.mjs",
        "tests/low-turnover.spec.mjs",
        "src/scripts/comparison-charts.mjs",
        "src/scripts/comparison-state.mjs",
        "src/i18n/comparison-en.json",
        "src/i18n/comparison-zh-CN.json",
        "tests/comparison.test.mjs",
        "tests/comparison.spec.mjs",
        "src/scripts/incremental-charts.mjs",
        "src/scripts/incremental-state.mjs",
        "src/i18n/incremental-en.json",
        "src/i18n/incremental-zh-CN.json",
        "tests/incremental-state.test.mjs",
        "tests/incremental.spec.mjs",
        "src/scripts/reader-charts.mjs",
        "src/scripts/predictive-charts.mjs",
        "tests/reader-charts.test.mjs",
        "tests/reader-charts.spec.mjs",
        "src/scripts/strategy-controls-charts.mjs",
        "src/scripts/strategy-controls-state.mjs",
        "tests/strategy-controls-fixture.mjs",
        "tests/strategy-controls-state.test.mjs",
        "tests/strategy-controls.spec.mjs",
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
    built_dir: Path, output_paths: set[str], errors: list[str], route: str = ""
) -> None:
    route_requirements = {
        f"{route}index.html": {
            "language": "en",
            "locale_switch": f"{PAGES_BASE_PATH}/zh-CN/{route}",
        },
        f"zh-CN/{route}index.html": {
            "language": "zh-CN",
            "locale_switch": f"{PAGES_BASE_PATH}/{route}",
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


def _same_editorial_facts(actual, expected) -> bool:
    """JSON numbers can differ in notation, but booleans are never numbers."""
    if type(expected) in (int, float):
        return type(actual) in (int, float) and actual == expected
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _same_editorial_facts(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _same_editorial_facts(a, b) for a, b in zip(actual, expected)
        )
    return actual == expected


def _expected_editorial_summary(snapshot: dict, readiness: dict) -> dict:
    """Independently project reviewed public rows into the compact home facts."""

    def group(market, fee, pool):
        rows = [
            r
            for r in snapshot["results"]
            if r["market"] == market
            and r["fee_bps"] == fee
            and (market == "crypto" or r["pool_id"] == pool)
        ]
        ids = {r["job_id"] for r in rows}
        pairs = [
            p
            for p in snapshot["crypto_pairs" if market == "crypto" else "us_pairs"]
            if p.get("job_id", p.get("candidate_job_id")) in ids
        ]
        requested = len({r["start"] for r in rows})
        return dict(
            poolId=pool,
            feeBps=fee,
            requestedWindows=requested,
            blockedWindows=requested - len(pairs),
            windows=len(pairs),
            returnWins=sum(p["net_return_change"] > 0 for p in pairs),
            drawdownWins=sum(p["drawdown_change"] < 0 for p in pairs),
            medianReturnChange=median(p["net_return_change"] for p in pairs)
            if pairs
            else None,
            medianDrawdownChange=median(p["drawdown_change"] for p in pairs)
            if pairs
            else None,
        )

    measured = snapshot["status"] == "measured"
    ranges = {}
    for market in ("US", "crypto"):
        rows = [r for r in snapshot["results"] if r["market"] == market]
        ranges[market] = (
            dict(start=min(r["start"] for r in rows), end=max(r["end"] for r in rows))
            if rows
            else None
        )
    observation = readiness["observation"]
    return dict(
        asOf=snapshot["as_of"],
        codeCommit=snapshot["code_commit"],
        planSha256=snapshot["plan_sha256"],
        coverage=dict(snapshot["coverage"]),
        observation=dict(
            status=observation["status"],
            observations=observation["observations"],
            firstEligibleObservationAt=observation["first_eligible_observation_at"],
        ),
        us=[
            group("US", 20, pool)
            for pool in ("exclude_nvda", "exclude_three", "fixed_six")
        ]
        if measured
        else [],
        crypto=[group("crypto", fee, "trend_vs_matched") for fee in (35, 50)]
        if measured
        else [],
        evidenceRange=ranges,
    )


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
    multipage = "src/pages/strategies.astro" in source_paths
    fact_outputs = REQUIRED_OUTPUT
    if multipage:
        fact_outputs = {"strategies/index.html", "zh-CN/strategies/index.html"}
        for route in ("strategies/", "factors/", "docs/project/"):
            required = {f"{route}index.html", f"zh-CN/{route}index.html"}
            if missing := required - output_paths:
                errors.append(f"required research page missing: {sorted(missing)}")
            _validate_localized_output(built_dir, output_paths, errors, route)
    snapshot = source_dir / "src/data/real-data-study.v1.json"
    if snapshot.is_file():
        from competition_tools.evaluation.study_publication import validate_public_study

        try:
            value = validate_public_study(
                json.loads(snapshot.read_text(encoding="utf-8"))
            )
            expected = {r["job_id"]: r for r in value["results"]}
            for relative in fact_outputs & output_paths:
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
    ablation_path = source_dir / "src/data/ablation-study.v1.json"
    if ablation_path.is_file():
        from competition_tools.evaluation.ablation_publication import (
            validate_public_ablation,
        )

        try:
            ablation = validate_public_ablation(
                json.loads(ablation_path.read_text(encoding="utf-8"))
            )
            expected_ablation = {r["job_id"]: r for r in ablation["results"]}
            for relative in fact_outputs & output_paths:
                metadata = _PageMetadata()
                metadata.feed((built_dir / relative).read_text(encoding="utf-8"))
                actual = {
                    key: json.loads(facts) for key, facts in metadata.ablation_facts
                }
                if actual != expected_ablation or len(metadata.ablation_facts) != len(
                    expected_ablation
                ):
                    errors.append("ablation facts differ from reviewed source snapshot")
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            errors.append("invalid public ablation snapshot or output")
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
    dex_path = source_dir / "src/data/dex-factor-readiness.v1.json"
    if dex_path.is_file():
        from competition_tools.evaluation.dex_factor_publication import (
            validate_public_dex_factors,
        )

        try:
            dex = validate_public_dex_factors(
                json.loads(dex_path.read_text(encoding="utf-8"))
            )
            if dex["status"] != "readiness_only":
                raise ValueError("Unreviewed measured presentation")
            for relative in ("factors/index.html", "zh-CN/factors/index.html"):
                metadata = _PageMetadata()
                metadata.feed((built_dir / relative).read_text(encoding="utf-8"))
                if (
                    len(metadata.dex_facts) != 1
                    or json.loads(metadata.dex_facts[0]) != dex
                ):
                    errors.append(
                        "DEX readiness facts differ from reviewed source snapshot"
                    )
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            errors.append("invalid public DEX readiness facts or output")
    controls_path = source_dir / "src/data/strategy-controls.v1.json"
    if controls_path.is_file():
        from competition_tools.evaluation.controls.publication import (
            validate_public_controls,
            REVIEWED_PUBLIC_CONTROLS,
        )
        from competition_tools.evaluation.study_identity import canonical_hash

        try:
            controls = validate_public_controls(
                json.loads(controls_path.read_text(encoding="utf-8"))
            )
            if (
                controls["status"] == "measured"
                and canonical_hash(controls) not in REVIEWED_PUBLIC_CONTROLS
            ):
                errors.append("unreviewed measured controls snapshot")
            for relative in ("strategies/index.html", "zh-CN/strategies/index.html"):
                metadata = _PageMetadata()
                metadata.feed((built_dir / relative).read_text(encoding="utf-8"))
                if (
                    len(metadata.controls_facts) != 1
                    or json.loads(metadata.controls_facts[0]) != controls
                ):
                    errors.append("controls facts differ from reviewed source snapshot")
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            errors.append("invalid public controls facts or output")
    robustness_path = source_dir / "src/data/strategy-robustness.v1.json"
    if robustness_path.is_file():
        from competition_tools.evaluation.robustness.publication import (
            validate_public_robustness,
        )

        try:
            robustness = validate_public_robustness(
                json.loads(robustness_path.read_text(encoding="utf-8"))
            )
            for relative in ("strategies/index.html", "zh-CN/strategies/index.html"):
                metadata = _PageMetadata()
                metadata.feed((built_dir / relative).read_text(encoding="utf-8"))
                if (
                    len(metadata.robustness_facts) != 1
                    or json.loads(metadata.robustness_facts[0]) != robustness
                ):
                    errors.append(
                        "robustness facts differ from reviewed source snapshot"
                    )
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            errors.append("invalid public robustness facts or output")
    readiness_path = source_dir / "src/data/strategy-readiness.v1.json"
    if readiness_path.is_file():
        from competition_tools.evaluation.research_readiness import (
            validate_public_readiness,
        )

        try:
            readiness = validate_public_readiness(
                json.loads(readiness_path.read_text(encoding="utf-8"))
            )
            for relative in ("strategies/index.html", "zh-CN/strategies/index.html"):
                metadata = _PageMetadata()
                metadata.feed((built_dir / relative).read_text(encoding="utf-8"))
                if (
                    len(metadata.readiness_facts) != 1
                    or json.loads(metadata.readiness_facts[0]) != readiness
                ):
                    errors.append(
                        "strategy readiness facts differ from reviewed source snapshot"
                    )
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            errors.append("invalid public strategy readiness facts or output")
    home_metadata = []
    for relative in ("index.html", "zh-CN/index.html"):
        page = _PageMetadata()
        if (built_dir / relative).is_file():
            page.feed((built_dir / relative).read_text(encoding="utf-8"))
        home_metadata.append(page)
    if any(p.editorial_facts for p in home_metadata):
        from competition_tools.evaluation.robustness.publication import (
            validate_public_robustness,
        )
        from competition_tools.evaluation.research_readiness import (
            validate_public_readiness,
        )

        try:
            snapshot = validate_public_robustness(
                json.loads(robustness_path.read_text(encoding="utf-8"))
            )
            readiness = validate_public_readiness(
                json.loads(readiness_path.read_text(encoding="utf-8"))
            )
            expected = _expected_editorial_summary(snapshot, readiness)
            for page in home_metadata:
                if len(page.editorial_facts) != 1 or not _same_editorial_facts(
                    json.loads(page.editorial_facts[0]), expected
                ):
                    errors.append(
                        "editorial facts differ from reviewed source snapshot"
                    )
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            errors.append("invalid public editorial facts or output")
    predictive_path = source_dir / "src/data/equity-predictive.v1.json"
    if predictive_path.is_file():
        from competition_tools.evaluation.predictive_publication import (
            validate_public_predictive,
        )

        try:
            predictive = validate_public_predictive(
                json.loads(predictive_path.read_text(encoding="utf-8"))
            )
            for name in ("factors/index.html", "zh-CN/factors/index.html"):
                page = _PageMetadata()
                page.feed((built_dir / name).read_text(encoding="utf-8"))
                if len(page.predictive_facts) != 1:
                    raise ValueError("Missing predictive facts")
                emitted = validate_public_predictive(
                    json.loads(page.predictive_facts[0])
                )
                if emitted != predictive:
                    raise ValueError("Changed predictive facts")
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            errors.append("invalid public predictive facts or output")
    incremental_path = source_dir / "src/data/incremental-research.v1.json"
    if incremental_path.is_file():
        from competition_tools.evaluation.incremental_publication import (
            validate_public_incremental,
        )

        try:
            expected = validate_public_incremental(
                json.loads(incremental_path.read_text(encoding="utf-8"))
            )
            for name in (
                "factors/index.html",
                "zh-CN/factors/index.html",
                "strategies/index.html",
                "zh-CN/strategies/index.html",
            ):
                page = _PageMetadata()
                page.feed((built_dir / name).read_text(encoding="utf-8"))
                if len(page.incremental_facts) != 1:
                    raise ValueError("Missing incremental facts")
                actual = validate_public_incremental(
                    json.loads(page.incremental_facts[0])
                )
                if actual != expected:
                    raise ValueError("Changed incremental facts")
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            errors.append("invalid public incremental facts or output")
    comparison_path = source_dir / "src/data/strategy-comparison.v1.json"
    if comparison_path.is_file():
        from competition_tools.evaluation.comparison_publication import (
            parse_public_comparison,
        )

        try:
            expected = parse_public_comparison(
                comparison_path.read_text(encoding="utf-8")
            )
            for name in (
                "factors/index.html",
                "zh-CN/factors/index.html",
                "strategies/index.html",
                "zh-CN/strategies/index.html",
            ):
                page = _PageMetadata()
                page.feed((built_dir / name).read_text(encoding="utf-8"))
                if len(page.comparison_facts) != 1:
                    raise ValueError("Missing comparison facts")
                actual = parse_public_comparison(page.comparison_facts[0])
                if actual != expected:
                    raise ValueError("Changed comparison facts")
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            errors.append("invalid public comparison facts or output")
    low_turnover_path = source_dir / "src/data/low-turnover.v1.json"
    if low_turnover_path.is_file():
        from .evaluation.low_turnover_publication import parse_reviewed

        try:
            expected = parse_reviewed(low_turnover_path.read_text(encoding="utf-8"))
            for topic in ("factors", "strategies"):
                expected_views = (
                    {("equity", "factor")}
                    if topic == "factors"
                    else {("equity", "strategy"), ("crypto", "strategy")}
                )
                for prefix in ("", "zh-CN/"):
                    page = _PageMetadata()
                    page.feed(
                        (built_dir / f"{prefix}{topic}/index.html").read_text(
                            encoding="utf-8"
                        )
                    )
                    if (
                        len(page.low_turnover_facts) != len(expected_views)
                        or {(m, v) for m, v, _ in page.low_turnover_facts}
                        != expected_views
                    ):
                        raise ValueError("Missing market/view research facts")
                    if any(
                        parse_reviewed(raw) != expected
                        for _, _, raw in page.low_turnover_facts
                    ):
                        raise ValueError("Changed low-turnover facts")
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            errors.append("invalid public low-turnover facts or output")
    followup_path = source_dir / "src/data/evidence-followup.v1.json"
    if followup_path.is_file():
        from .evaluation.followup_publication import (
            parse_reviewed as parse_followup,
            summary,
        )

        try:
            expected = summary(
                parse_followup(followup_path.read_text(encoding="utf-8"))
            )
            progress_topics = ["strategies/", "factors/"]
            if any(page.progress_facts for page in home_metadata):
                progress_topics.insert(0, "")
            for prefix in ("", "zh-CN/"):
                for topic in progress_topics:
                    page = _PageMetadata()
                    page.feed(
                        (built_dir / f"{prefix}{topic}index.html").read_text(
                            encoding="utf-8"
                        )
                    )
                    if len(page.progress_facts) != 1 or not _same_editorial_facts(
                        json.loads(page.progress_facts[0]), expected
                    ):
                        raise ValueError("Missing or changed progress facts")
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            errors.append("invalid public follow-up facts or output")
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
            "strategy-controls",
            "execution-evidence",
            "observation-registry",
            "strategy-robustness",
            "data-refresh",
            "native-process-diagnostics",
            "equity-predictive",
            "incremental-research",
            "strategy-comparison",
            "cnn-chart-research",
        )
    }
    if "strategies/index.html" in output_paths:
        for prefix, locale, other in (("", "en", "zh-CN/"), ("zh-CN/", "zh-CN", "")):
            expected[f"{prefix}docs/project/index.html"] = (
                locale,
                f"{PAGES_BASE_PATH}/{other}docs/project/",
            )
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
