"""Explicit Paper API readiness and opt-in use of the existing IBC wrapper."""

import argparse
import json
import logging
import re
import subprocess
import sys
from pathlib import Path

from competition_tools import gateway_launcher as gl
from .paths import validate_external


def result(state, code, *, attempted=False):
    return {
        "schema_version": "competition.gateway_readiness.v1",
        "state": state,
        "code": code,
        "startup_attempted": attempted,
        "api": "connected" if state == "ready" else "not_ready",
        "account_identity": "not_checked",
        "historical_data": "not_checked",
        "read_only_client": state == "ready",
    }


def probe_api(connection_file: Path, *, timeout=2, client_factory=None) -> dict:
    try:
        source = validate_external(connection_file)
        connection = json.loads(source.read_text(encoding="utf-8-sig"))
        if (
            set(connection) != {"host", "port", "client_id"}
            or connection["host"] != "127.0.0.1"
            or type(connection["port"]) is not int
            or connection["port"] != 4002
            or type(connection["client_id"]) is not int
            or not 0 < connection["client_id"] < 2**31
            or not 0.1 <= timeout <= 5
        ):
            return result("blocked", "INVALID_PAPER_CONNECTION")
    except (OSError, ValueError, TypeError, KeyError):
        return result("blocked", "INVALID_PAPER_CONNECTION")
    if client_factory is None:
        try:
            from ib_insync import IB
        except ImportError:
            return result("blocked", "BROKER_DATA_PROFILE_REQUIRED")
        client_factory = IB
    client = None
    logger = logging.getLogger("ib_insync")
    level = logger.level
    logger.setLevel(logging.CRITICAL)
    outcome = result("blocked", "API_PROBE_FAILED")
    try:
        client = client_factory()
        client.connect(
            connection["host"],
            connection["port"],
            clientId=connection["client_id"],
            timeout=timeout,
            readonly=True,
        )
        outcome = (
            result("ready", "API_READY")
            if client.isConnected()
            else result("not_ready", "GATEWAY_API_NOT_READY")
        )
    except (ConnectionError, OSError, TimeoutError):
        outcome = result("not_ready", "GATEWAY_API_NOT_READY")
    except Exception:
        # Unexpected SDK/programming failures must not trigger a login attempt.
        outcome = result("blocked", "API_PROBE_FAILED")
    finally:
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                outcome = result("blocked", "API_DISCONNECT_FAILED")
        logger.setLevel(level)
    return outcome


def ensure_gateway(
    connection_file: Path,
    *,
    launcher_config=None,
    workspace=None,
    wrapper=None,
    environment=None,
) -> dict:
    initial = probe_api(connection_file)
    if initial["state"] != "not_ready":
        return initial | {"startup_attempted": False}
    if sys.platform != "win32":
        return result("blocked", "WINDOWS_LAUNCHER_REQUIRED")
    if any(value is None for value in (launcher_config, workspace, wrapper)):
        return result("blocked", "GATEWAY_LAUNCH_CONFIGURATION_REQUIRED")
    try:
        spec = gl.build_launch_spec(launcher_config, workspace)
        if not spec["status"]["activation_authorized"]:
            return result("blocked", "ACTIVATION_NOT_AUTHORIZED")
        if not spec["launcher_ready"] or not spec["start_supported"]:
            return result("blocked", "PREPARE_REQUIRED")
        wrapper = validate_external(Path(wrapper))
        module = wrapper.with_name("PaperGateway.psm1")
        if (
            wrapper.name != "Start-PaperGateway.ps1"
            or not wrapper.is_file()
            or not module.is_file()
        ):
            return result("blocked", "GATEWAY_WRAPPER_REQUIRED")
        if not gl.owner_only_acl(wrapper) or not gl.owner_only_acl(module):
            return result("blocked", "UNSAFE_ACL")
    except gl.LauncherError as error:
        return result("blocked", str(error))
    except (OSError, ValueError, TypeError, KeyError):
        return result("blocked", "GATEWAY_LAUNCH_CONFIGURATION_INVALID")
    command = [
        "pwsh",
        "-NoLogo",
        "-NoProfile",
        "-File",
        str(wrapper),
        "-Action",
        "ensure",
        "-PythonPath",
        sys.executable,
        "-ConfigPath",
        str(launcher_config),
        "-WorkspacePath",
        str(workspace),
        "-ApiConnectionPath",
        str(connection_file),
    ]
    try:
        # Windows run() kills only the wrapper on timeout, never the Gateway tree.
        # The existing launch lease is retained when startup becomes uncertain.
        child = subprocess.run(
            command,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=330,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        status = json.loads(child.stdout)
        if not isinstance(status, dict):
            return result("blocked", "GATEWAY_START_FAILED", attempted=True)
        if child.returncode == 0 and status.get("state") == "api_ready":
            verified = probe_api(connection_file)
            return verified | {"startup_attempted": True}
        code = status.get("code", "GATEWAY_AUTHENTICATION_OR_API_NOT_READY")
        if not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code):
            code = "GATEWAY_START_FAILED"
        return result("blocked", code, attempted=True)
    except subprocess.TimeoutExpired:
        return result("blocked", "GATEWAY_START_OBSERVATION_TIMEOUT", attempted=True)
    except (OSError, ValueError, TypeError):
        return result("blocked", "GATEWAY_START_FAILED", attempted=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only Paper API probe, without login"
    )
    parser.add_argument("--connection-file", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=2)
    args = parser.parse_args(argv)
    value = probe_api(args.connection_file, timeout=args.timeout)
    print(json.dumps(value))
    return (
        0 if value["state"] == "ready" else (3 if value["state"] == "not_ready" else 2)
    )


if __name__ == "__main__":
    raise SystemExit(main())
