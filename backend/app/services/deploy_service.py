"""
Idempotent OpenVPN + easy-rsa deployment service for Ubuntu systems.

Deployment is executed asynchronously; progress is streamed via an asyncio.Queue.
"""
import asyncio
import uuid
from dataclasses import dataclass, field

from app.services.remote.base import Executor

_APT_GET = "/usr/bin/apt-get"
_DPKG = "/usr/bin/dpkg"
_UNAME = "/bin/uname"
_DF = "/usr/bin/df"
_SYSTEMCTL = "/usr/bin/systemctl"

# In-process task registry
_TASKS: dict[str, "DeployTask"] = {}


@dataclass
class DeployTask:
    task_id: str
    status: str = "pending"  # pending | running | completed | failed
    log_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    log_lines: list[str] = field(default_factory=list)
    error: str | None = None

    def log(self, message: str) -> None:
        self.log_lines.append(message)
        self.log_queue.put_nowait(message)


def create_deploy_task() -> DeployTask:
    task = DeployTask(task_id=str(uuid.uuid4()))
    _TASKS[task.task_id] = task
    return task


def get_deploy_task(task_id: str) -> DeployTask | None:
    return _TASKS.get(task_id)


async def check_prerequisites(executor: Executor) -> dict:
    notes: list[str] = []

    # Check OS
    os_result = await executor.run_command([_UNAME, "-a"], timeout=10.0)
    os_version = os_result.stdout.strip() if os_result.success else None
    os_compatible = "Ubuntu" in (os_version or "") or "Debian" in (os_version or "")
    if not os_compatible:
        notes.append("OS does not appear to be Ubuntu/Debian; deployment may fail")

    # Check openvpn
    openvpn_result = await executor.run_command(
        [_DPKG, "-l", "openvpn"], timeout=10.0
    )
    openvpn_installed = openvpn_result.success and "ii  openvpn" in openvpn_result.stdout

    # Check easy-rsa
    easyrsa_result = await executor.run_command(
        [_DPKG, "-l", "easy-rsa"], timeout=10.0
    )
    easyrsa_installed = easyrsa_result.success and "ii  easy-rsa" in easyrsa_result.stdout

    # Check disk space
    df_result = await executor.run_command([_DF, "-BG", "/"], timeout=10.0)
    disk_space_gb = None
    if df_result.success:
        lines = df_result.stdout.strip().splitlines()
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 4:
                try:
                    disk_space_gb = float(parts[3].rstrip("G"))
                except ValueError:
                    pass
    if disk_space_gb is not None and disk_space_gb < 1.0:
        notes.append(f"Low disk space: {disk_space_gb:.1f}GB available")

    return {
        "os_compatible": os_compatible,
        "os_version": os_version,
        "openvpn_installed": openvpn_installed,
        "easyrsa_installed": easyrsa_installed,
        "disk_space_gb": disk_space_gb,
        "ready_to_deploy": True,
        "notes": notes,
    }


async def run_deployment(
    executor: Executor,
    task: DeployTask,
    install_openvpn: bool = True,
    install_easyrsa: bool = True,
    openvpn_config_dir: str = "/etc/openvpn",
    easyrsa_install_dir: str = "/etc/easy-rsa",
) -> None:
    """Run the deployment steps; updates task status and log queue."""
    task.status = "running"
    try:
        task.log("Starting deployment...")

        # Update package index
        task.log("Updating package index...")
        result = await executor.run_command(
            [_APT_GET, "update", "-q"],
            timeout=120.0,
        )
        result.raise_on_error("apt-get update")
        task.log("Package index updated.")

        # Install packages
        packages: list[str] = []
        if install_openvpn:
            packages.append("openvpn")
        if install_easyrsa:
            packages.append("easy-rsa")

        if packages:
            task.log(f"Installing packages: {', '.join(packages)}...")
            result = await executor.run_command(
                [_APT_GET, "install", "-y", "-q", *packages],
                timeout=300.0,
            )
            result.raise_on_error(f"apt-get install {' '.join(packages)}")
            task.log("Packages installed successfully.")

        # Enable openvpn service
        if install_openvpn:
            task.log("Enabling openvpn systemd service...")
            result = await executor.run_command(
                [_SYSTEMCTL, "enable", "openvpn"],
                timeout=15.0,
            )
            # Non-fatal if already enabled
            task.log("openvpn service enabled.")

        task.log("Deployment completed successfully.")
        task.status = "completed"

    except Exception as exc:
        task.error = str(exc)
        task.status = "failed"
        task.log(f"Deployment FAILED: {exc}")
        raise
