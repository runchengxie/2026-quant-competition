"""Install independently locked packages only for the requested profile."""

from pathlib import Path
import subprocess
import tomllib

from .config import TeamConfig
from .paths import validate_external
from .processes import child_environment, envelope, interpreter, run_child

PROJECTS = {
    "root": ".",
    "equity-lab": "research/equity-lab",
    "crypto-mm": "research/crypto-mm",
    "platform-compare": "research/platform-compare",
}


def verify_repository(path: Path) -> Path:
    root = path.resolve()
    try:
        metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        if metadata["project"]["name"] != "hk-competition-execution":
            raise ValueError("Wrong repository")
        if not all(
            (root / relative / "uv.lock").is_file() for relative in PROJECTS.values()
        ):
            raise ValueError("Incomplete repository")
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError("Invalid repository") from exc
    return root


def setup(
    config: TeamConfig, repository_root: Path, profile: str, *, uv_executable="uv"
) -> dict:
    projects = []
    try:
        root = verify_repository(repository_root)
        validate_external(config.data_root)
        validate_external(config.environment_root)
    except ValueError:
        return envelope("setup", issues=["INVALID_REPOSITORY"])
    if profile not in {"offline", "framework", "broker-data", "daily-data", "website"}:
        return envelope("setup", issues=["INVALID_PROFILE"])
    names = {
        "offline": ["root", "equity-lab", "crypto-mm"],
        "framework": ["platform-compare"],
        "broker-data": ["root"],
        "daily-data": ["root"],
        "website": [],
    }[profile]
    launcher = (
        [uv_executable] if isinstance(uv_executable, str) else list(uv_executable)
    )
    try:
        destinations = {
            name: validate_external(config.environment_root / name) for name in names
        }
    except ValueError:
        return envelope("setup", issues=["INVALID_ENVIRONMENT"])
    try:
        for name in names:
            environment = child_environment(config)
            environment["UV_PROJECT_ENVIRONMENT"] = str(destinations[name])
            argv = [
                *launcher,
                "sync",
                "--locked",
                "--project",
                str(root / PROJECTS[name]),
            ]
            if profile == "broker-data":
                argv += ["--extra", "ibkr"]
            elif profile == "daily-data":
                argv += ["--extra", "daily-data"]
            child = run_child(argv, environment=environment, timeout=900)
            if child.returncode:
                return envelope(
                    "setup", issues=["CHILD_COMMAND_FAILED"], projects=projects
                )
            if not interpreter(config, name).is_file():
                return envelope(
                    "setup", issues=["ENVIRONMENT_UNAVAILABLE"], projects=projects
                )
            projects.append({"name": name, "ready": True})
        if profile == "website":
            # npm's launcher is a .cmd file on Windows; invoke Node's JS entry without a shell.
            import shutil

            npm = shutil.which("npm")
            node = shutil.which("node")
            if not npm or not node:
                return envelope("setup", issues=["TOOL_UNAVAILABLE"])
            if Path(npm).suffix.lower() == ".cmd":
                argv = [node, str(Path(npm).parent / "node_modules/npm/bin/npm-cli.js")]
            else:
                argv = [npm]
            child = run_child(
                [*argv, "ci", "--prefix", str(root / "site")],
                environment=child_environment(config),
                timeout=900,
            )
            if child.returncode:
                return envelope("setup", issues=["CHILD_COMMAND_FAILED"])
            projects.append({"name": "website", "ready": True})
    except OSError:
        return envelope("setup", issues=["TOOL_UNAVAILABLE"], projects=projects)
    except subprocess.TimeoutExpired:
        return envelope("setup", issues=["CHILD_TIMEOUT"], projects=projects)
    return envelope("setup", projects=projects)
