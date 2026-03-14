"""Integration tests for server management endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_local_server(client: AsyncClient, superuser, superuser_token: str):
    response = await client.post(
        "/api/v1/servers",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={"name": "local-server", "is_local": True, "description": "Test local server"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "local-server"
    assert data["is_local"] is True


@pytest.mark.asyncio
async def test_create_server_requires_superuser(client: AsyncClient, regular_user, user_token: str):
    response = await client.post(
        "/api/v1/servers",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"name": "test-server", "is_local": True},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_servers(client: AsyncClient, superuser, superuser_token: str):
    # Create a server first
    await client.post(
        "/api/v1/servers",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={"name": "list-test-server", "is_local": True},
    )
    response = await client.get(
        "/api/v1/servers",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_server_not_found(client: AsyncClient, superuser, superuser_token: str):
    response = await client.get(
        "/api/v1/servers/99999",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_server_invalid_name(client: AsyncClient, superuser, superuser_token: str):
    response = await client.post(
        "/api/v1/servers",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={"name": "invalid name with spaces!", "is_local": True},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_server(client: AsyncClient, superuser, superuser_token: str):
    create_resp = await client.post(
        "/api/v1/servers",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={"name": "to-delete", "is_local": True},
    )
    server_id = create_resp.json()["id"]

    delete_resp = await client.delete(
        f"/api/v1/servers/{server_id}",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert delete_resp.status_code == 204

    get_resp = await client.get(
        f"/api/v1/servers/{server_id}",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_update_server(client: AsyncClient, superuser, superuser_token: str):
    create_resp = await client.post(
        "/api/v1/servers",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={"name": "update-test", "is_local": True},
    )
    server_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/api/v1/servers/{server_id}",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={"description": "Updated description"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["description"] == "Updated description"
