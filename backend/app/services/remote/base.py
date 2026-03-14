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
        "/usr/share/easy-rsa/easyrsa",
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


def _validate_binary(cmd: list[str]) -> None:
    """Raise if the binary is not in the allowed whitelist."""
    from app.core.exceptions import RemoteExecutionError

    if not cmd:
        raise RemoteExecutionError("Empty command")

    binary = cmd[0]
    if binary not in ALLOWED_BINARIES:
        raise RemoteExecutionError(
            f"Execution of '{binary}' is not permitted. "
            "Only whitelisted system binaries may be invoked."
        )

    # Prevent path traversal in the binary itself
    if ".." in binary:
        raise RemoteExecutionError("Binary path must not contain '..'")
