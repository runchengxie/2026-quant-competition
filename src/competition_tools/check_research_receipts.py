"""Exercise synthetic leaf producers and the root consumer in separate environments."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from competition_tools.research_acceptance import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", choices=("equity-lab", "crypto-mm"), required=True)
    parser.add_argument("--leaf-python", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        root = args.output_root.resolve()
        root.mkdir(parents=True, exist_ok=False)
        data = root / "fixture"
        data.mkdir()
        crypto = args.project == "crypto-mm"
        package = "crypto_mm" if crypto else "equity_lab"
        # Only this static fixture generator runs in the leaf interpreter.
        code = (
            f"from {package}.demo import build_demo_data; "
            "from pathlib import Path; import sys,json; "
            "print(json.dumps([str(p) for p in build_demo_data(Path(sys.argv[1]))]))"
        )
        env = dict(os.environ, DATA_ROOT=str(root))
        produced = subprocess.run(
            [str(args.leaf_python), "-c", code, str(data)],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        paths = [
            Path(path).resolve(strict=True) for path in json.loads(produced.stdout)
        ]
        if not paths or any(
            not path.is_relative_to(data) or not path.is_file() for path in paths
        ):
            raise ValueError("UNSAFE_FIXTURE_OUTPUT")
        manifest = {
            "schema_version": "competition.research_input_manifest.v1",
            "dataset_root": str(data),
            "producer": {
                "package": "competition-" + args.project,
                "package_version": "0.1.0",
                "code_revision": "unknown",
            },
            "dataset_id": "synthetic-contract-fixture-v1",
            "market": "CRYPTO" if crypto else "HK",
            "synthetic": True,
            "source_state": "synthetic",
            "timezone": "unknown" if crypto else "Asia/Hong_Kong",
            "price_basis": "raw",
            "universe_state": "synthetic",
            "availability_state": "unknown",
            "files": [
                {
                    "relative_path": p.relative_to(data).as_posix(),
                    "kind": p.parent.name if crypto else "daily_bars",
                    "sha256": sha256_file(p),
                    "size_bytes": p.stat().st_size,
                }
                for p in paths
            ],
        }
        path = root / "manifest.json"
        path.write_text(json.dumps(manifest, allow_nan=False), encoding="utf-8")
        receipt = root / "receipt.json"
        subprocess.run(
            [
                str(args.leaf_python),
                "-m",
                package + (".commands.validate_inputs" if crypto else ".validation"),
                "--manifest",
                str(path),
                "--output",
                str(receipt),
            ],
            env=env,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "competition_tools.research_acceptance",
                "--receipt",
                str(receipt),
                "--dataset-root",
                str(data),
            ],
            check=True,
            capture_output=True,
        )
        print(
            json.dumps(
                {
                    "status": "passed",
                    "project": args.project,
                    "purpose": "synthetic_contract_check",
                }
            )
        )
        return 0
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError):
        print(
            json.dumps(
                {"status": "blocked", "issue_codes": ["RESEARCH_CONTRACT_CHECK_FAILED"]}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
