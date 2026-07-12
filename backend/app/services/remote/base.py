"""
Executor abstraction — the single security boundary for all system command execution.

Every command executed on local or remote servers MUST go through an Executor.
The allowed binary whitelist is enforced here before any execution occurs.
"""
from dataclasses import dataclass, field
from typing import Protocol

# Exact absolute paths of every binary the application is permitted to invoke.
# This prevents command injection even if an attacker controls argument values.
ALLOWED_BINARIES: frozenset[str] = frozenset(
    [
        "/usr/sbin/openvpn",
        "/usr/bin/easy-rsa",
        "/usr/bin/easyrsa",
        "/usr/share/easy-rsa/easyrsa",
        "/usr/local/bin/easyrsa",
        "/usr/local/share/easy-rsa/easyrsa",
        # systemctl
        "/bin/systemctl",
        "/usr/bin/systemctl",
        # network
        "/sbin/ip",
        "/usr/sbin/ip",
        "/bin/ip",
        # user management
        "/usr/sbin/useradd",
        "/usr/sbin/usermod",
        "/usr/sbin/userdel",
        "/usr/bin/passwd",
        "/usr/bin/id",
        "/usr/bin/groups",
        "/usr/bin/getent",
        "/usr/sbin/groupadd",
        "/usr/sbin/groupdel",
        # file operations
        "/bin/cat",
        "/usr/bin/cat",
        "/bin/ls",
        "/usr/bin/ls",
        "/bin/mkdir",
        "/usr/bin/mkdir",
        "/bin/cp",
        "/usr/bin/cp",
        "/bin/mv",
        "/usr/bin/mv",
        "/bin/chmod",
        "/usr/bin/chmod",
        "/bin/chown",
        "/usr/bin/chown",
        "/bin/tar",
        "/usr/bin/tar",
        "/bin/rm",
        "/usr/bin/rm",
        "/usr/bin/sha256sum",
        "/usr/bin/find",
        # certificate operations
        "/usr/bin/openssl",
        # password management
        "/usr/sbin/chpasswd",
        # package management
        "/usr/bin/apt-get",
        "/usr/bin/dpkg",
        # journald logs
        "/usr/bin/journalctl",
        # privilege escalation (required for backup of root-owned files)
        "/usr/bin/sudo",
        # miscellaneous
        "/usr/bin/df",
        "/bin/uname",
        "/usr/bin/uname",
        "/bin/hostname",
        "/usr/bin/hostname",
        # iptables
        "/usr/sbin/iptables",
        "/sbin/iptables",
        # sysctl
        "/usr/sbin/sysctl",
        "/sbin/sysctl",
    ]
)


@dataclass
class ExecutionResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0

    def raise_on_error(self, context: str = "") -> "ExecutionResult":
        from app.core.exceptions import RemoteExecutionError

        if not self.success:
            msg = f"{context}: exit {self.returncode}"
            if self.stderr:
                msg += f" — {self.stderr[:512]}"
            raise RemoteExecutionError(msg)
        return self


class Executor(Protocol):
    """Protocol all executors must implement."""

    async def run_command(
        self,
        cmd: list[str],
        timeout: float = 30.0,
        stdin_data: bytes | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecutionResult: ...

    async def read_file(self, path: str) -> bytes: ...

    async def write_file(self, path: str, content: bytes, mode: int = 0o644) -> None: ...

    async def file_exists(self, path: str) -> bool: ...

    async def list_directory(self, path: str) -> list[str]: ...


_SUDO = "/usr/bin/sudo"


def prepare_sudo_command(
    cmd: list[str],
    sudo_password: str | None,
    preserve_env: bool = False,
) -> tuple[list[str], bytes | None]:
    """Wrap a command with sudo and return (cmd, stdin_data).

    If sudo_password is set, uses ``sudo -S`` (read password from stdin).
    Otherwise uses ``sudo -n`` (non-interactive / NOPASSWD).
    """
    flags = ["-S"] if sudo_password else ["-n"]
    if preserve_env:
        flags.append("-E")
    stdin_data = f"{sudo_password}\n".encode() if sudo_password else None
    return [_SUDO, *flags, *cmd], stdin_data


def _validate_binary(cmd: list[str]) -> None:
    """Raise if the binary is not in the allowed whitelist.

    When the command is wrapped in ``sudo``, the whitelist is enforced on the
    REAL binary being run under sudo (after sudo's own flags), not just on
    ``sudo`` itself — otherwise the whitelist would be a no-op for every
    privileged command.
    """
    from app.core.exceptions import RemoteExecutionError

    if not cmd:
        raise RemoteExecutionError("Empty command")

    idx = 0
    if cmd[0] == _SUDO:
        idx = 1
        while idx < len(cmd) and cmd[idx].startswith("-"):
            idx += 1  # skip sudo flags (-S / -n / -E)
        if idx >= len(cmd):
            raise RemoteExecutionError("sudo invoked without a target binary")

    binary = cmd[idx]
    if binary not in ALLOWED_BINARIES:
        raise RemoteExecutionError(
            f"Execution of '{binary}' is not permitted. "
            "Only whitelisted system binaries may be invoked."
        )

    # Prevent path traversal in the binary itself
    if ".." in binary:
        raise RemoteExecutionError("Binary path must not contain '..'")
