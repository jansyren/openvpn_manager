"""Session-security tests: refresh-token revocation (SEC-4) and login rate limiting (SEC-6)."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_refresh_token_revoked_after_logout(client: AsyncClient, superuser):
    """After logout, the refresh token must not be usable to mint new access tokens."""
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"}
    )
    assert login.status_code == 200
    access_token = login.json()["access_token"]

    # Capture the refresh token the server set, before logout clears the cookie.
    refresh_cookie = client.cookies.get("refresh_token")
    assert refresh_cookie is not None

    logout = await client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert logout.status_code == 200

    # Re-present the (now revoked) refresh token explicitly.
    reused = await client.post(
        "/api/v1/auth/refresh", cookies={"refresh_token": refresh_cookie}
    )
    assert reused.status_code == 401


@pytest.mark.asyncio
async def test_login_is_rate_limited(client: AsyncClient):
    """Exceeding the per-IP login limit returns 429. The limiter is disabled in the
    test env by default (so it doesn't interfere with other tests); enable it just
    for this test and reset its storage afterward. We use a throwaway username so
    the rate-limit probing does not trip the (session-global) account-lockout state
    for a username other tests rely on. 429 is raised by middleware before the auth
    handler, so it fires regardless of the username's validity."""
    from app.core.rate_limit import limiter
    from app.core.security import clear_failed_logins

    probe = "ratelimit-probe"
    limiter.enabled = True
    limiter.reset()
    try:
        statuses = []
        for _ in range(12):  # LOGIN_RATE_LIMIT_PER_MINUTE is 10 in the test env
            r = await client.post(
                "/api/v1/auth/login",
                json={"username": probe, "password": "WrongPassword!"},
            )
            statuses.append(r.status_code)
        assert 429 in statuses, f"expected a 429 among {statuses}"
    finally:
        limiter.reset()
        limiter.enabled = False
        clear_failed_logins(probe)
