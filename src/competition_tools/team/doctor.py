"""Local-only environment readiness; no provider imports or authentication."""

from .config import TeamConfig
from .processes import envelope, interpreter


def diagnose(config: TeamConfig) -> dict:
    projects = [
        {"name": name, "ready": interpreter(config, name).is_file()}
        for name in ("root", "equity-lab", "crypto-mm")
    ]
    return envelope(
        "doctor",
        projects=projects,
        issues=[] if all(p["ready"] for p in projects) else ["ENVIRONMENT_UNAVAILABLE"],
    )
