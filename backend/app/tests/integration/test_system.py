"""Endpoint tests for the system router (NTH-9)."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_is_public_and_ok(client: AsyncClient):
    resp = await client.get("/api/v1/system/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


@pytest.mark.asyncio
async def test_info_requires_auth(client: AsyncClient):
    assert (await client.get("/api/v1/system/info")).status_code == 401


@pytest.mark.asyncio
async def test_info_returns_version(client: AsyncClient, superuser, superuser_token: str):
    resp = await client.get(
        "/api/v1/system/info", headers={"Authorization": f"Bearer {superuser_token}"}
    )
    assert resp.status_code == 200
    assert resp.json()["app_version"]


@pytest.mark.asyncio
async def test_audit_log_requires_superuser(client: AsyncClient, regular_user, user_token: str):
    resp = await client.get(
        "/api/v1/system/audit-log", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert resp.status_code == 403
