"""
Remote executor — runs commands on a remote server via SSH using asyncssh.

Key security properties:
- Binary whitelist enforced before command is sent
- SSH host key fingerprint validation (TOFU on first connect)
- SSH private key decrypted in memory only for the duration of the connection
- Connection pooled per server to reduce authentication overhead
"""
import asyncio
import shlex
from typing import TYPE_CHECKING

import asyncssh

from app.core.exceptions import RemoteExecutionError
from app.core.security import decrypt_ssh_key, decrypt_sudo_password
from app.services.remote.base import ExecutionResult, _validate_binary

if TYPE_CHECKING:
    from app.db.models.server import Server

# Connection pool: server_id → SSHClientConnection
_CONNECTION_POOL: dict[int, asyncssh.SSHClientConnection] = {}
_POOL_LOCK = asyncio.Lock()


async def get_connection(server: "Server") -> asyncssh.SSHClientConnection:
    async with _POOL_LOCK:
        existing = _CONNECTION_POOL.get(server.id)
        if existing is not None:
            try:
                # Health check: send a keepalive-style command
                await existing.run("true", timeout=5)
                return existing
            except Exception:
                _CONNECTION_POOL.pop(server.id, None)

        conn = await _create_connection(server)
        _CONNECTION_POOL[server.id] = conn
        return conn


async def _create_connection(server: "Server") -> asyncssh.SSHClientConnection:
    if not server.ssh_key_encrypted_blob:
        raise RemoteExecutionError(f"No SSH key configured for server {server.name}")

    private_key_pem = decrypt_ssh_key(server.ssh_key_encrypted_blob)
    try:
        private_key = asyncssh.import_private_key(private_key_pem)
        conn = await asyncssh.connect(
            server.host,
            port=server.port,
            username=server.ssh_username,
            client_keys=[private_key],
            known_hosts=None,  # fingerprint validated manually below (TOFU)
            connect_timeout=15,
        )
    except asyncssh.PermissionDenied as exc:
        raise RemoteExecutionError(f"SSH authentication failed for {server.host}") from exc
    except (OSError, asyncssh.Error) as exc:
        raise RemoteExecutionError(f"SSH connection failed to {server.host}: {exc}") from exc
    finally:
        private_key_pem = b"\x00" * len(private_key_pem)

    # TOFU: if a fingerprint has already been recorded, verify it hasn't changed
    if server.ssh_host_fingerprint is not None:
        host_key = conn.get_server_host_key()
        fingerprint = host_key.get_fingerprint() if host_key else None
        if fingerprint != server.ssh_host_fingerprint:
            conn.close()
            raise RemoteExecutionError(
                f"SSH host key mismatch for {server.host}: "
                f"expected {server.ssh_host_fingerprint!r}, got {fingerprint!r}"
            )

    return conn


class RemoteExecutor:
    def __init__(self, server: "Server") -> None:
        self._server = server
        self._sudo_password: str | None = None
        if server.sudo_password_encrypted_blob:
            self._sudo_password = decrypt_sudo_password(server.sudo_password_encrypted_blob)

    @property
    def sudo_password(self) -> str | None:
        return self._sudo_password

    async def run_command(
        self,
        cmd: list[str],
        timeout: float = 30.0,
        stdin_data: bytes | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecutionResult:
        _validate_binary(cmd)
        command_str = shlex.join(cmd)
        if env:
            env_prefix = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
            command_str = f"{env_prefix} {command_str}"

        conn = await get_connection(self._server)
        try:
            result = await conn.run(
                command_str,
                input=stdin_data.decode() if stdin_data else None,
                timeout=timeout,
            )
        except asyncssh.TimeoutError as exc:
            raise RemoteExecutionError(
                f"Command '{cmd[0]}' timed out after {timeout}s on {self._server.host}"
            ) from exc
        except asyncssh.Error as exc:
            raise RemoteExecutionError(f"SSH error executing command: {exc}") from exc

        return ExecutionResult(
            returncode=result.exit_status or 0,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )

    async def read_file(self, path: str) -> bytes:
        self._validate_path(path)
        conn = await get_connection(self._server)
        try:
            async with conn.start_sftp_client() as sftp:
                async with sftp.open(path, "rb") as f:
                    return await f.read()
        except asyncssh.SFTPError as exc:
            raise RemoteExecutionError(f"Cannot read remote file {path}: {exc}") from exc

    async def write_file(self, path: str, content: bytes, mode: int = 0o644) -> None:
        self._validate_path(path)
        conn = await get_connection(self._server)
        tmp_path = path + ".tmp"
        try:
            async with conn.start_sftp_client() as sftp:
                async with sftp.open(tmp_path, "wb") as f:
                    await f.write(content)
                await sftp.chmod(tmp_path, mode)
                await sftp.rename(tmp_path, path)
        except asyncssh.SFTPError as exc:
            raise RemoteExecutionError(f"Cannot write remote file {path}: {exc}") from exc

    async def file_exists(self, path: str) -> bool:
        self._validate_path(path)
        conn = await get_connection(self._server)
        try:
            async with conn.start_sftp_client() as sftp:
                await sftp.stat(path)
                return True
        except asyncssh.SFTPNoSuchFile:
            return False
        except asyncssh.SFTPPermissionDenied as exc:
            raise RemoteExecutionError(
                f"Permission denied reading {path} via SFTP — "
                "ensure the SSH user has read access to the PKI directory"
            ) from exc
        except asyncssh.SFTPError:
            return False

    async def list_directory(self, path: str) -> list[str]:
        self._validate_path(path)
        conn = await get_connection(self._server)
        try:
            async with conn.start_sftp_client() as sftp:
                entries = await sftp.listdir(path)
                return [f"{path}/{e}" for e in entries]
        except asyncssh.SFTPError as exc:
            raise RemoteExecutionError(f"Cannot list remote directory {path}: {exc}") from exc

    @staticmethod
    def _validate_path(path: str) -> None:
        if ".." in path:
            raise RemoteExecutionError("Path must not contain '..'")
        if not path.startswith("/"):
            raise RemoteExecutionError("Path must be absolute")
