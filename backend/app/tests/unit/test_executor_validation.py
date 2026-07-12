"""Unit tests for the executor binary whitelist, incl. the sudo path (NTH-6/B14)."""
import pytest

from app.core.exceptions import RemoteExecutionError
from app.services.remote.base import _validate_binary, prepare_sudo_command


def test_allows_whitelisted_binary():
    _validate_binary(["/usr/sbin/openvpn", "--version"])  # no raise


def test_rejects_non_whitelisted_binary():
    with pytest.raises(RemoteExecutionError):
        _validate_binary(["/usr/bin/whoami"])


def test_validates_real_binary_under_sudo():
    # sudo-wrapping a whitelisted binary is allowed...
    cmd, _ = prepare_sudo_command(["/usr/sbin/openvpn", "--version"], sudo_password=None)
    _validate_binary(cmd)  # no raise

    # ...but sudo-wrapping a NON-whitelisted binary must still be rejected
    # (the pre-fix behaviour only checked argv[0] == sudo and let this through).
    evil, _ = prepare_sudo_command(["/usr/bin/whoami"], sudo_password="pw")  # noqa: S106
    with pytest.raises(RemoteExecutionError):
        _validate_binary(evil)


def test_rejects_sudo_without_target():
    with pytest.raises(RemoteExecutionError):
        _validate_binary(["/usr/bin/sudo", "-n"])
