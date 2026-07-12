"""Unit tests for security utilities."""
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.core.security import (
    _LOCKOUT_TRACKER,
    clear_failed_logins,
    compute_sha256,
    decrypt_ssh_key,
    encrypt_ssh_key,
    hash_password,
    is_account_locked,
    record_failed_login,
    verify_password,
)


def test_password_hash_and_verify():
    hashed = hash_password("SuperSecret123!")
    assert hashed != "SuperSecret123!"
    assert verify_password("SuperSecret123!", hashed)
    assert not verify_password("wrongpassword", hashed)


def test_password_hashes_are_unique():
    h1 = hash_password("SamePassword1!")
    h2 = hash_password("SamePassword1!")
    assert h1 != h2  # bcrypt uses a random salt


def test_compute_sha256():
    digest = compute_sha256(b"hello world")
    assert digest == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    # Correct value
    import hashlib
    assert compute_sha256(b"hello world") == hashlib.sha256(b"hello world").hexdigest()


def test_ssh_key_encryption_roundtrip():
    original = b"-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n-----END RSA PRIVATE KEY-----\n"
    with patch("app.core.security.get_settings") as mock_settings:
        mock_settings.return_value.ssh_key_encryption_secret = "test-secret-for-unit-tests-only"
        encrypted = encrypt_ssh_key(original)
        assert encrypted != original
        decrypted = decrypt_ssh_key(encrypted)
        assert decrypted == original


def test_ssh_key_encryption_uses_nonce():
    """Two encryptions of the same data should produce different ciphertexts."""
    data = b"test key data"
    with patch("app.core.security.get_settings") as mock_settings:
        mock_settings.return_value.ssh_key_encryption_secret = "test-secret-for-unit-tests-only"
        enc1 = encrypt_ssh_key(data)
        enc2 = encrypt_ssh_key(data)
        assert enc1 != enc2


def test_lockout_after_max_attempts():
    username = "lockout_test_user"
    _LOCKOUT_TRACKER.pop(username, None)

    with patch("app.core.security.get_settings") as mock_settings:
        mock_settings.return_value.max_failed_login_attempts = 3
        mock_settings.return_value.lockout_duration_minutes = 1

        assert not record_failed_login(username)  # 1st fail
        assert not record_failed_login(username)  # 2nd fail
        locked = record_failed_login(username)    # 3rd fail → locked
        assert locked
        assert is_account_locked(username)

    _LOCKOUT_TRACKER.pop(username, None)


def test_clear_failed_logins():
    username = "clear_test_user"
    _LOCKOUT_TRACKER[username] = (3, time.time() + 600)
    clear_failed_logins(username)
    assert not is_account_locked(username)
    assert username not in _LOCKOUT_TRACKER
