from pathlib import Path
import re

SITE = Path(__file__).parent
ALLOWED = {"index.html", "styles.css", "content-check.py"}
SENSITIVE = {
    "credential": re.compile(
        r"(?i)(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{30,}|"
        r"sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
    ),
    "account_or_order_identifier": re.compile(
        r"(?i)\b(?:account[_ -]?id|account[_ -]?number|order[_ -]?id)\s*[:=]\s*[A-Z0-9-]{5,}"
    ),
}


def main() -> int:
    entries = list(SITE.iterdir())
    files = {path.name for path in entries if path.is_file()}
    unexpected = {path.name for path in entries} - ALLOWED
    missing = {"index.html", "styles.css"} - files
    errors = []
    if unexpected:
        errors.append(f"unexpected files in Pages input: {sorted(unexpected)}")
    if missing:
        errors.append(f"required site files missing: {sorted(missing)}")
    for path in entries:
        if path.is_file() and path.suffix in {".html", ".css"}:
            contents = path.read_text(encoding="utf-8")
            for label, pattern in SENSITIVE.items():
                if pattern.search(contents):
                    errors.append(
                        f"sensitive pattern ({label}) detected in {path.name}"
                    )
    if errors:
        print("\n".join(errors))
        return 1
    print(
        "Pages input check passed: only allowlisted static files; no sensitive patterns found."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
