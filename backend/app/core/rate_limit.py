"""Shared rate limiter (slowapi).

The limiter is keyed on the client IP. When the app runs behind a trusted
reverse proxy, the real client IP arrives in X-Forwarded-For; we honour its
first hop, mirroring `dependencies.get_client_ip`. This assumes the proxy is
trusted — do not expose the app directly if you rely on these limits.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config import get_settings


def client_ip_key(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


_settings = get_settings()

limiter = Limiter(
    key_func=client_ip_key,
    default_limits=[f"{_settings.rate_limit_per_minute}/minute"],
    enabled=_settings.rate_limit_enabled,
)

# Stricter limit string for the login endpoint, applied via decorator.
LOGIN_RATE_LIMIT = f"{_settings.login_rate_limit_per_minute}/minute"
