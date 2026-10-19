"""Run the team's stdlib-only entry from a source checkout."""

from pathlib import Path
import sys

root = Path(__file__).resolve().parent
if not (root / "src/competition_tools/team/__main__.py").is_file():
    raise SystemExit("Team entry is missing from this checkout")
sys.path.insert(0, str(root / "src"))

from competition_tools.team.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
