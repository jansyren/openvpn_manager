"""
Manages OpenVPN systemd service units via systemctl.

Service names follow the pattern 'openvpn@<instance_name>'.
All instance names are validated against a safe pattern before use.
"""
import re

from app.core.exceptions import RemoteExecutionError, ValidationError
from app.services.remote.base import Executor

_SAFE_INSTANCE_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")

# systemctl binary — will be resolved at runtime from the whitelist
_SYSTEMCTL = "/usr/bin/systemctl"
_SYSTEMCTL_ALT = "/bin/systemctl"


def _systemctl_bin(executor: Executor) -> str:
    # Both paths are in the whitelist; prefer /usr/bin
    return _SYSTEMCTL


def _service_name(instance_name: str) -> str:
    if not _SAFE_INSTANCE_RE.match(instance_name):
        raise ValidationError(f"Invalid instance name: {instance_name!r}")
    return f"openvpn@{instance_name}.service"


async def service_action(executor: Executor, instance_name: str, action: str) -> dict:
    """Run a systemctl action on an OpenVPN instance.

    Uses sudo when a sudo password is configured on the executor (required when
    the SSH user is not root). Falls back to a direct call when no password is
    stored, which works for root sessions or NOPASSWD polkit setups.

    Returns a dict with 'returncode', 'stdout', 'stderr'.
    """
    from app.services.remote.base import prepare_sudo_command

    allowed_actions = {"start", "stop", "restart", "reload", "enable", "disable", "status"}
    if action not in allowed_actions:
        raise ValidationError(f"Invalid service action: {action!r}")

    service = _service_name(instance_name)
    base_cmd = [_systemctl_bin(executor), action, service]

    sudo_pw = getattr(executor, "sudo_password", None)
    if sudo_pw is not None:
        cmd, stdin_data = prepare_sudo_command(base_cmd, sudo_pw)
    else:
        cmd, stdin_data = base_cmd, None

    result = await executor.run_command(cmd, timeout=30.0, stdin_data=stdin_data)

    # 'status' returns exit 3 when stopped — not an error
    if action == "status" or result.success:
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    result.raise_on_error(f"systemctl {action} {service}")
    return {}  # unreachable


async def get_service_status(executor: Executor, instance_name: str) -> dict:
    """Return parsed status info for the service."""
    raw = await service_action(executor, instance_name, "status")
    stdout = raw.get("stdout", "")

    status = "unknown"
    active_since = None
    pid = None

    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("Active:"):
            if "running" in line:
                status = "active"
            elif "failed" in line:
                status = "failed"
            elif "inactive" in line:
                status = "inactive"
            elif "activating" in line:
                status = "activating"
            # Extract since timestamp
            if "since" in line:
                active_since = line.split("since", 1)[-1].strip().split(";")[0].strip()
        elif line.startswith("Main PID:"):
            try:
                pid = int(line.split()[2])
            except (IndexError, ValueError):
                pass

    return {"status": status, "active_since": active_since, "pid": pid}


async def get_service_logs(executor: Executor, instance_name: str, lines: int = 100) -> str:
    """Return the last N lines of journald logs for this service."""
    from app.services.remote.base import prepare_sudo_command

    if lines < 1 or lines > 10000:
        raise ValidationError("lines must be between 1 and 10000")

    service = _service_name(instance_name)
    journalctl = "/usr/bin/journalctl"
    base_cmd = [journalctl, "-u", service, "-n", str(lines), "--no-pager"]

    sudo_pw = getattr(executor, "sudo_password", None)
    if sudo_pw is not None:
        cmd, stdin_data = prepare_sudo_command(base_cmd, sudo_pw)
    else:
        cmd, stdin_data = base_cmd, None

    result = await executor.run_command(cmd, timeout=15.0, stdin_data=stdin_data)
    return result.stdout
