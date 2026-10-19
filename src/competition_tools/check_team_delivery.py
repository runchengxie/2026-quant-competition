"""Verify installed core environments contain no quant framework distributions."""

import argparse
import json
from pathlib import Path

from competition_tools.team.config import load_config
from competition_tools.team.processes import child_environment, interpreter, run_child


def check(config) -> dict:
    inventories = {}
    for name in ("root", "equity-lab", "crypto-mm"):
        child = run_child(
            [
                str(interpreter(config, name)),
                "-c",
                "import importlib.metadata as m,json;print(json.dumps(sorted(d.metadata['Name'] for d in m.distributions())))",
            ],
            environment=child_environment(config),
            timeout=30,
        )
        if child.returncode:
            raise ValueError("Unable to inspect core environment")
        names = json.loads(child.stdout)
        if any(
            item.lower()
            .replace("_", "-")
            .startswith(("quant-", "portfolio-backtester", "research-contracts"))
            for item in names
        ):
            raise ValueError("A core environment contains a framework distribution")
        inventories[name] = names
    return {"schema_version": "competition.team_inventory.v1", "projects": inventories}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(load_config(args.config)), indent=2))


if __name__ == "__main__":
    main()
