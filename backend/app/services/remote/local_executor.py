"""
Local executor — runs commands on the same machine using asyncio.create_subprocess_exec.

Key security properties:
- shell=False is enforced: no shell metacharacter expansion
- Binary whitelist checked before every execution
- Configurable timeout per command
- Passwords are passed via stdin pipe, never on the command line
"""
import asyncio
import os
from pathlib import Path

from app.core.exceptions import RemoteExecutionError
from app.services.remote.base import ALLOWED_BINARIES, ExecutionResult, _validate_binary


class LocalExecutor:
    async def run_command(
        self,
        cmd: list[str],
        timeout: float = 30.0,
        stdin_data: bytes | None = None,
        env: dict[str, str] | None = None,
    ) -> ExecutionResult:
        _validate_binary(cmd)

        stdin_pipe = asyncio.subprocess.PIPE if stdin_data is not None else asyncio.subprocess.DEVNULL
        merged_env = {**os.environ, **(env or {})} if env else None

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=stdin_pipe,
                env=merged_env,
            )

            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(input=stdin_data),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise RemoteExecutionError(
                    f"Command '{cmd[0]}' timed out after {timeout}s"
                )

            return ExecutionResult(
                returncode=proc.returncode or 0,
                stdout=stdout_b.decode("utf-8", errors="replace"),
                stderr=stderr_b.decode("utf-8", errors="replace"),
            )

        except FileNotFoundError as exc:
            raise RemoteExecutionError(f"Binary not found: {cmd[0]}") from exc

    async def read_file(self, path: str) -> bytes:
        self._validate_path(path)
        try:
            return Path(path).read_bytes()
        except OSError as exc:
            raise RemoteExecutionError(f"Cannot read file {path}: {exc}") from exc

    async def write_file(self, path: str, content: bytes, mode: int = 0o644) -> None:
        self._validate_path(path)
        p = Path(path)
        tmp_path = p.with_suffix(".tmp")
        try:
            tmp_path.write_bytes(content)
            os.chmod(tmp_path, mode)
            tmp_path.rename(p)
        except OSError as exc:
            tmp_path.unlink(missing_ok=True)
            raise RemoteExecutionError(f"Cannot write file {path}: {exc}") from exc

    async def file_exists(self, path: str) -> bool:
        self._validate_path(path)
        try:
            Path(path).stat()
            return True
        except FileNotFoundError:
            return False
        except PermissionError as exc:
            raise RemoteExecutionError(f"Permission denied reading {path}") from exc

    async def list_directory(self, path: str) -> list[str]:
        self._validate_path(path)
        try:
            return [str(p) for p in Path(path).iterdir()]
        except OSError as exc:
            raise RemoteExecutionError(f"Cannot list directory {path}: {exc}") from exc

    @staticmethod
    def _validate_path(path: str) -> None:
        if ".." in path:
            raise RemoteExecutionError("Path must not contain '..'")
        if not path.startswith("/"):
            raise RemoteExecutionError("Path must be absolute")
