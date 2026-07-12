import contextlib
import hashlib
import os
import time
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
import bcrypt
from jose import JWTError, jwt

from app.config import get_settings
from app.core.exceptions import AuthError

# In-memory token blacklist (JTI → expiry timestamp)
_TOKEN_BLACKLIST: OrderedDict[str, float] = OrderedDict()
_BLACKLIST_MAX_SIZE = 10_000

# In-memory lockout tracker: username → (fail_count, locked_until_ts)
_LOCKOUT_TRACKER: dict[str, tuple[int, float]] = {}

# Lazily-created Redis client (only when REDIS_URL is configured). When present,
# the token blacklist and login-lockout live in Redis so they survive restarts
# and are shared across workers/replicas; otherwise the in-memory dicts above are
# used (correct only for a single worker). Redis errors fail open (fall back to
# in-memory) so a Redis outage never locks everyone out.
_redis_client: Any = None
_redis_resolved = False


def _get_redis() -> Any:
    global _redis_client, _redis_resolved
    if not _redis_resolved:
        _redis_resolved = True
        url = get_settings().redis_url
        if url:
            import redis

            _redis_client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)
    return _redis_client


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


async def hash_password_async(password: str) -> str:
    """bcrypt (~100ms at rounds=12) off the event loop, for use in async handlers."""
    return await anyio.to_thread.run_sync(hash_password, password)


async def verify_password_async(plain: str, hashed: str) -> bool:
    return await anyio.to_thread.run_sync(verify_password, plain, hashed)


def _prune_blacklist() -> None:
    now = time.time()
    expired = [jti for jti, exp in _TOKEN_BLACKLIST.items() if exp < now]
    for jti in expired:
        del _TOKEN_BLACKLIST[jti]
    # Cap size
    while len(_TOKEN_BLACKLIST) > _BLACKLIST_MAX_SIZE:
        _TOKEN_BLACKLIST.popitem(last=False)


def blacklist_token(jti: str, expires_at: datetime) -> None:
    if not jti:
        return
    r = _get_redis()
    if r is not None:
        ttl = max(1, int(expires_at.timestamp() - time.time()))
        with contextlib.suppress(Exception):
            r.setex(f"bl:{jti}", ttl, "1")
            return
    _prune_blacklist()
    _TOKEN_BLACKLIST[jti] = expires_at.timestamp()


def is_token_blacklisted(jti: str) -> bool:
    if not jti:
        return False
    r = _get_redis()
    if r is not None:
        with contextlib.suppress(Exception):
            return bool(r.exists(f"bl:{jti}"))
    _prune_blacklist()
    return jti in _TOKEN_BLACKLIST


def create_access_token(subject: str | int, additional_claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    jti = os.urandom(16).hex()

    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "jti": jti,
        "type": "access",
    }
    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(payload, settings.jwt_private_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    subject: str | int, additional_claims: dict[str, Any] | None = None
) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)
    jti = os.urandom(16).hex()

    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "jti": jti,
        "type": "refresh",
    }
    if additional_claims:
        payload.update(additional_claims)

    token = jwt.encode(payload, settings.jwt_private_key, algorithm=settings.jwt_algorithm)
    return token, expire


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_public_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise AuthError("Invalid or expired token") from exc

    if payload.get("type") != expected_type:
        raise AuthError(f"Expected {expected_type} token")

    jti = payload.get("jti", "")
    if is_token_blacklisted(jti):
        raise AuthError("Token has been revoked")

    return payload


# --- Lockout ---

def record_failed_login(username: str) -> bool:
    """Returns True if the account is now locked."""
    settings = get_settings()
    r = _get_redis()
    if r is not None:
        with contextlib.suppress(Exception):
            if r.exists(f"lock:{username}"):
                return True
            count = r.incr(f"fail:{username}")
            # Bound the fail counter's lifetime so it can't accumulate forever.
            r.expire(f"fail:{username}", settings.lockout_duration_minutes * 60)
            if count >= settings.max_failed_login_attempts:
                r.setex(f"lock:{username}", settings.lockout_duration_minutes * 60, "1")
                r.delete(f"fail:{username}")
                return True
            return False

    now = time.time()
    count, locked_until = _LOCKOUT_TRACKER.get(username, (0, 0.0))

    if locked_until > now:
        return True  # already locked

    count += 1
    if count >= settings.max_failed_login_attempts:
        locked_until = now + settings.lockout_duration_minutes * 60
        _LOCKOUT_TRACKER[username] = (count, locked_until)
        return True

    _LOCKOUT_TRACKER[username] = (count, 0.0)
    return False


def is_account_locked(username: str) -> bool:
    r = _get_redis()
    if r is not None:
        with contextlib.suppress(Exception):
            return bool(r.exists(f"lock:{username}"))

    now = time.time()
    _, locked_until = _LOCKOUT_TRACKER.get(username, (0, 0.0))
    if locked_until > now:
        return True
    return False


def clear_failed_logins(username: str) -> None:
    r = _get_redis()
    if r is not None:
        with contextlib.suppress(Exception):
            r.delete(f"fail:{username}", f"lock:{username}")
            return
    _LOCKOUT_TRACKER.pop(username, None)


# --- SSH key encryption (AES-256-GCM via HKDF) ---

def _derive_ssh_encryption_key(label: str = "ssh-key-encryption") -> bytes:
    settings = get_settings()
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=label.encode(),
    )
    return hkdf.derive(settings.ssh_key_encryption_secret.encode())


def encrypt_ssh_key(private_key_pem: bytes) -> bytes:
    key = _derive_ssh_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, private_key_pem, None)
    return nonce + ciphertext


def decrypt_ssh_key(blob: bytes) -> bytes:
    key = _derive_ssh_encryption_key()
    aesgcm = AESGCM(key)
    nonce, ciphertext = blob[:12], blob[12:]
    return aesgcm.decrypt(nonce, ciphertext, None)


def encrypt_sudo_password(password: str) -> bytes:
    key = _derive_ssh_encryption_key(label="sudo-password-encryption")
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, password.encode(), None)
    return nonce + ciphertext


def decrypt_sudo_password(blob: bytes) -> str:
    key = _derive_ssh_encryption_key(label="sudo-password-encryption")
    aesgcm = AESGCM(key)
    nonce, ciphertext = blob[:12], blob[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()


def encrypt_ca_passphrase(passphrase: str) -> bytes:
    key = _derive_ssh_encryption_key(label="ca-passphrase-encryption")
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, passphrase.encode(), None)
    return nonce + ciphertext


def decrypt_ca_passphrase(blob: bytes) -> str:
    key = _derive_ssh_encryption_key(label="ca-passphrase-encryption")
    aesgcm = AESGCM(key)
    nonce, ciphertext = blob[:12], blob[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()


def encrypt_ldap_password(password: str) -> bytes:
    key = _derive_ssh_encryption_key(label="ldap-bind-password-encryption")
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, password.encode(), None)
    return nonce + ciphertext


def decrypt_ldap_password(blob: bytes) -> str:
    key = _derive_ssh_encryption_key(label="ldap-bind-password-encryption")
    aesgcm = AESGCM(key)
    nonce, ciphertext = blob[:12], blob[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
