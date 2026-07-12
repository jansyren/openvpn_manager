"""Endpoint tests for the certificates router (NTH-9)."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_certificates_requires_auth(client: AsyncClient):
    assert (await client.get("/api/v1/certificates")).status_code == 401


@pytest.mark.asyncio
async def test_list_certificates_empty(client: AsyncClient, superuser, superuser_token: str):
    resp = await client.get(
        "/api/v1/certificates", headers={"Authorization": f"Bearer {superuser_token}"}
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_revoke_requires_superuser(client: AsyncClient, regular_user, user_token: str):
    # get_current_superuser gates the endpoint before the handler runs, so a
    # non-superuser is rejected regardless of whether the certificate exists.
    resp = await client.post(
        "/api/v1/certificates/1/revoke",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"reason": "unspecified"},
    )
    assert resp.status_code == 403
