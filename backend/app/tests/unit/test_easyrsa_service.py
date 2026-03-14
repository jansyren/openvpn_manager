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


def make_executor(returncode: int = 0, stdout: str = "OK", stderr: str = "") -> AsyncMock:
    mock = AsyncMock()
    mock.run_command.return_value = ExecutionResult(
        returncode=returncode, stdout=stdout, stderr=stderr
    )
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
