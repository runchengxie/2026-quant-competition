"""Explicit finite robustness delivery through independent leaf CLIs."""

from pathlib import Path

from ..evaluation.controls.contracts import read_json
from ..evaluation.robustness.plan import freeze_robustness
from ..evaluation.robustness.runner import run_robustness
from ..evaluation.study_identity import source_identity
from .processes import envelope


def execute(config, spec_path: Path, output_root: Path) -> dict:
    freeze_robustness(read_json(spec_path), output_root, code_identity=source_identity(Path(__file__).resolve().parents[3]))
    result = run_robustness(config, output_root / "plan.json")
    return envelope("robustness", issues=[] if result["status"] == "completed" else ["ROBUSTNESS_PARTIAL"], projects=[result])
