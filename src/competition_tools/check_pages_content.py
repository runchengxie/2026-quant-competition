import argparse
from pathlib import Path, PurePosixPath
import re
from typing import Callable


SENSITIVE = {
    "credential": re.compile(
        r"(?i)(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{30,}|"
        r"sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
    ),
    "credential_assignment": re.compile(
        r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*[\"']?[A-Za-z0-9/_+=.-]{24,}"
    ),
    "account_or_order_identifier": re.compile(
        r"(?i)\b(?:account[_ -]?id|account[_ -]?number|order[_ -]?id)\s*[:=]\s*[A-Z0-9-]{5,}"
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
TEXT_SUFFIXES = {".astro", ".css", ".html", ".js", ".json", ".mjs", ".svg"}
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


def _allowed_source(relative_path: PurePosixPath) -> bool:
    path = relative_path.as_posix()
    if path in {
        "astro.config.mjs",
        "package.json",
        "package-lock.json",
        "tsconfig.json",
    }:
        return True
    if path.startswith("src/"):
        return relative_path.suffix in {".astro", ".css"}
    if path.startswith("public/"):
        return relative_path.suffix.lower() in PUBLIC_ASSET_SUFFIXES
    return False


def _allowed_output(relative_path: PurePosixPath) -> bool:
    return relative_path.suffix.lower() in ASSET_SUFFIXES | {".html"}


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
        if ignored_directories.intersection(relative_path.parts):
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

    _scan_sensitive(source_files, "source", errors)
    _scan_sensitive(output_files, "output", errors)
    return errors


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
