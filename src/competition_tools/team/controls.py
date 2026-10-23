"""The opt-in controls boundary, independent of legacy evaluation dispatch."""

from pathlib import Path

from .config import TeamConfig
from .processes import envelope
from ..evaluation.controls.contracts import load_spec
from ..evaluation.controls.plan import freeze_controls
from ..evaluation.study_identity import source_identity


def execute(config: TeamConfig, spec_path: Path, output_root: Path) -> dict:
    spec = load_spec(spec_path)
    try:
        from ..evaluation.controls.runner import run_controls
    except ModuleNotFoundError as error:
        if error.name != "competition_tools.evaluation.controls.runner":
            raise
        # The runner is independently delivered after the scientific leaves.
        return envelope("controls", issues=["CONTROLS_RUNNER_UNAVAILABLE"])
    freeze_controls(
        spec,
        output_root,
        code_identity=source_identity(Path(__file__).resolve().parents[3]),
    )
    result = run_controls(config, output_root / "plan.json")
    issues = [] if result["status"] == "completed" else ["CONTROLS_PARTIAL"]
    return envelope("controls", issues=issues, projects=[result])
