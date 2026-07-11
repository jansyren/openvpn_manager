"""Unit tests for easy-rsa service — mocked subprocess."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import RemoteExecutionError, ValidationError
from app.services.easyrsa_service import (
    _validate_cn,
    _validate_path,
    build_client_full,
    init_pki,
)
from app.services.remote.base import ExecutionResult


def make_executor(
    returncode: int = 0,
    stdout: str = "OK",
    stderr: str = "",
    file_exists: dict[str, bool] | None = None,
) -> AsyncMock:
    mock = AsyncMock()
    mock.run_command.return_value = ExecutionResult(
        returncode=returncode, stdout=stdout, stderr=stderr
    )
    exists_map = file_exists or {}
    mock.file_exists.side_effect = lambda path: exists_map.get(path, False)
    return mock


def test_validate_cn_valid():
    _validate_cn("my-client-01")
    _validate_cn("VPN_Server")
    _validate_cn("site.example.com")


def test_validate_cn_invalid():
    with pytest.raises(ValidationError):
        _validate_cn("invalid CN with spaces")
    with pytest.raises(ValidationError):
        _validate_cn("../etc/passwd")
    with pytest.raises(ValidationError):
        _validate_cn("")


def test_validate_path_absolute():
    _validate_path("/usr/share/easy-rsa/easyrsa")
    _validate_path("/etc/easy-rsa")


def test_validate_path_rejects_traversal():
    with pytest.raises(ValidationError):
        _validate_path("/etc/easy-rsa/../../../etc/passwd")


def test_validate_path_rejects_relative():
    with pytest.raises(ValidationError):
        _validate_path("relative/path")


@pytest.mark.asyncio
async def test_init_pki_calls_correct_command():
    executor = make_executor(stdout="init-pki complete")
    result = await init_pki(executor, "/usr/share/easy-rsa/easyrsa", "/etc/easy-rsa/pki")
    assert result == "init-pki complete"
    executor.run_command.assert_called_once()
    cmd = executor.run_command.call_args[0][0]
    assert cmd[0] == "/usr/share/easy-rsa/easyrsa"
    assert "init-pki" in cmd


@pytest.mark.asyncio
async def test_build_client_full_passes_ca_passphrase_via_stdin():
    executor = make_executor(stdout="build-client-full complete")
    await build_client_full(
        executor,
        "/usr/share/easy-rsa/easyrsa",
        "/etc/easy-rsa/pki",
        "myclient",
        "ca-pass-phrase",
    )
    call_kwargs = executor.run_command.call_args
    # Passphrase passed via stdin_data, not in command args
    stdin_data = call_kwargs.kwargs.get("stdin_data") or call_kwargs[1].get("stdin_data")
    assert stdin_data is not None
    assert b"ca-pass-phrase" in stdin_data
    # Passphrase NOT in command args
    cmd = call_kwargs[0][0]
    assert "ca-pass-phrase" not in " ".join(cmd)


@pytest.mark.asyncio
async def test_init_pki_raises_on_failure():
    executor = make_executor(returncode=1, stderr="PKI init failed")
    with pytest.raises(RemoteExecutionError):
        await init_pki(executor, "/usr/share/easy-rsa/easyrsa", "/etc/easy-rsa/pki")


@pytest.mark.asyncio
async def test_build_client_full_removes_stale_unsigned_request():
    """A leftover reqs/<cn>.req from a previously failed build (e.g. wrong CA
    passphrase) should be cleared automatically so the retry can succeed,
    since easy-rsa refuses to overwrite an existing request file."""
    executor = make_executor(
        stdout="build-client-full complete",
        file_exists={"/etc/easy-rsa/pki/reqs/myclient.req": True},
    )
    await build_client_full(
        executor,
        "/usr/share/easy-rsa/easyrsa",
        "/etc/easy-rsa/pki",
        "myclient",
        "ca-pass-phrase",
    )

    rm_calls = [
        c for c in executor.run_command.call_args_list if c[0][0][:2] == ["/bin/rm", "-f"]
    ]
    assert len(rm_calls) == 1
    assert rm_calls[0][0][0][2] == "/etc/easy-rsa/pki/reqs/myclient.req"

    build_calls = [c for c in executor.run_command.call_args_list if "build-client-full" in c[0][0]]
    assert len(build_calls) == 1


@pytest.mark.asyncio
async def test_build_client_full_raises_when_certificate_already_issued():
    """If a signed cert already exists, don't delete anything or retry the
    build — surface a clear error instead of easy-rsa's cryptic CLI message."""
    executor = make_executor(
        file_exists={"/etc/easy-rsa/pki/issued/myclient.crt": True},
    )
    with pytest.raises(ValidationError):
        await build_client_full(
            executor,
            "/usr/share/easy-rsa/easyrsa",
            "/etc/easy-rsa/pki",
            "myclient",
            "ca-pass-phrase",
        )
    executor.run_command.assert_not_called()
