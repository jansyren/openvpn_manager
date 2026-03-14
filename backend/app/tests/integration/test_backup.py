"""Integration tests for backup endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_backups_empty(client: AsyncClient, superuser, superuser_token: str):
    response = await client.get(
        "/api/v1/backup",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_backup_not_found(client: AsyncClient, superuser, superuser_token: str):
    response = await client.get(
        "/api/v1/backup/99999",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_backup_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/backup")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_restore_requires_sha256_format(client: AsyncClient, superuser, superuser_token: str):
    """Restore endpoint must validate SHA-256 format."""
    response = await client.post(
        "/api/v1/backup/1/restore",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={"backup_id": 1, "expected_sha256": "not-a-valid-sha256"},
    )
    assert response.status_code == 422
