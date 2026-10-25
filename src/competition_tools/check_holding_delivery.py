"""Exercise separately installed synthetic ML producer and stdlib consumer."""

import argparse
import json
from pathlib import Path

from .datasets.daily_storage import safe_path
from .evaluation.low_turnover_evidence import verify_holding_export
from .team.config import TeamConfig
from .team.processes import child_environment, run_child


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leaf-python", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    # POSIX venv interpreters are symlinks. Keep the selected environment's
    # lexical path: resolving it would run the base Python without leaf deps.
    python = args.leaf_python
    output = safe_path(args.output_root)
    if (
        not python.is_absolute()
        or ".." in python.parts
        or not python.is_file()
        or output.exists()
    ):
        raise ValueError("INVALID_HOLDING_DELIVERY_PATHS")
    child = run_child(
        [
            str(python),
            "-I",
            "-m",
            "equity_lab.predictive.holding_demo",
            "--output",
            str(output),
        ],
        environment=child_environment(TeamConfig(output.parent, output.parent)),
        timeout=600,
    )
    if child.returncode:
        raise ValueError("SYNTHETIC_HOLDING_PRODUCER_FAILED")
    result = verify_holding_export(output)
    print(
        json.dumps(
            dict(
                status="completed",
                synthetic=True,
                accounts=len(result["accounts"]),
                fit_attempts=result["fit_attempts"],
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
