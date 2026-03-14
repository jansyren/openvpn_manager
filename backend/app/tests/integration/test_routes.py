"""Integration tests for route management endpoints."""
import pytest
from httpx import AsyncClient


async def create_server(client: AsyncClient, token: str, name: str) -> int:
    resp = await client.post(
        "/api/v1/servers",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "is_local": True},
    )
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_route(client: AsyncClient, superuser, superuser_token: str):
    server_id = await create_server(client, superuser_token, "route-server")

    response = await client.post(
        "/api/v1/routes",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={
            "server_id": server_id,
            "source_tun": "tun0",
            "dest_tun": "tun1",
            "destination_network": "10.9.0.0/24",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["source_tun"] == "tun0"
    assert data["dest_tun"] == "tun1"
    assert data["destination_network"] == "10.9.0.0/24"
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_create_route_invalid_tun(client: AsyncClient, superuser, superuser_token: str):
    server_id = await create_server(client, superuser_token, "route-server-2")
    response = await client.post(
        "/api/v1/routes",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={
            "server_id": server_id,
            "source_tun": "eth0",  # Not a tun interface
            "dest_tun": "tun1",
            "destination_network": "10.9.0.0/24",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_route_invalid_network(client: AsyncClient, superuser, superuser_token: str):
    server_id = await create_server(client, superuser_token, "route-server-3")
    response = await client.post(
        "/api/v1/routes",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={
            "server_id": server_id,
            "source_tun": "tun0",
            "dest_tun": "tun1",
            "destination_network": "not-a-network",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_routes(client: AsyncClient, superuser, superuser_token: str):
    response = await client.get(
        "/api/v1/routes",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_delete_route(client: AsyncClient, superuser, superuser_token: str):
    server_id = await create_server(client, superuser_token, "route-server-del")
    create_resp = await client.post(
        "/api/v1/routes",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={
            "server_id": server_id,
            "source_tun": "tun0",
            "dest_tun": "tun1",
            "destination_network": "10.10.0.0/24",
        },
    )
    route_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/routes/{route_id}",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert del_resp.status_code == 204
