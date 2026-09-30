from pathlib import Path
import re

SITE = Path(__file__).resolve().parents[1] / "site"
ALLOWED = {"index.html", "styles.css"}
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


def main() -> int:
    entries = list(SITE.rglob("*"))
    errors = []
    files = [path for path in entries if path.is_file() and not path.is_symlink()]
    allowed_paths = {path.relative_to(SITE).as_posix() for path in files}
    unexpected = [
        path.relative_to(SITE).as_posix()
        for path in entries
        if path.is_symlink()
        or not path.is_file()
        or path.relative_to(SITE).as_posix() not in ALLOWED
    ]
    missing = {"index.html", "styles.css"} - allowed_paths
    if unexpected:
        errors.append(f"unexpected Pages paths: {sorted(unexpected)}")
    if missing:
        errors.append(f"required site files missing: {sorted(missing)}")
    for path in files:
        contents = path.read_text(encoding="utf-8")
        for label, pattern in SENSITIVE.items():
            if pattern.search(contents):
                errors.append(f"sensitive pattern ({label}) detected in {path.name}")
    if errors:
        print("\n".join(errors))
        return 1
    print(
        "Pages input check passed: only allowlisted static files; no sensitive patterns found."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
