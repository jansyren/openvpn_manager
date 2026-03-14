"""Integration tests for authentication endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, superuser):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Admin123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, superuser):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "WrongPassword!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "doesnotmatter"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient, superuser, superuser_token: str):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["is_superuser"] is True


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, superuser, superuser_token: str):
    response = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 200

    # Token should be blacklisted now
    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert me_response.status_code == 401


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient, superuser, superuser_token: str):
    response = await client.put(
        "/api/v1/auth/me/password",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={"current_password": "Admin123!", "new_password": "NewAdmin456!"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(client: AsyncClient, superuser, superuser_token: str):
    response = await client.put(
        "/api/v1/auth/me/password",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={"current_password": "wrongpassword", "new_password": "NewAdmin456!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_change_password_complexity(client: AsyncClient, superuser, superuser_token: str):
    """New password must meet complexity requirements."""
    response = await client.put(
        "/api/v1/auth/me/password",
        headers={"Authorization": f"Bearer {superuser_token}"},
        json={"current_password": "Admin123!", "new_password": "weakpassword"},
    )
    assert response.status_code == 422
