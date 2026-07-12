"""Integration tests for operator-level permissions on the Users admin page.

Operators must be able to view the user list (so they can find and generate
certificates for vpn_user accounts) and delete vpn_user accounts, but must never
be able to create users, change anyone's role, or delete non-vpn_user accounts.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.user import User


@pytest_asyncio.fixture
async def operator_user(db_session: AsyncSession) -> User:
    user = User(
        username="operator1",
        hashed_password=hash_password("Operator123!"),
        role="operator",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def operator_token(client: AsyncClient, operator_user: User) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "operator1", "password": "Operator123!"},
    )
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def vpn_user_account(db_session: AsyncSession) -> User:
    user = User(
        username="vpnaccount",
        hashed_password=hash_password("Whatever123!"),
        role="vpn_user",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def viewer_account(db_session: AsyncSession) -> User:
    user = User(
        username="vieweraccount",
        hashed_password=hash_password("Whatever123!"),
        role="viewer",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_operator_can_list_users(client: AsyncClient, operator_user: User, operator_token: str):
    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_operator_cannot_create_user(client: AsyncClient, operator_user: User, operator_token: str):
    response = await client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"username": "newperson", "password": "Whatever123!", "role": "vpn_user"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_operator_cannot_change_role(
    client: AsyncClient, operator_user: User, operator_token: str, vpn_user_account: User
):
    response = await client.put(
        f"/api/v1/users/{vpn_user_account.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_operator_can_delete_vpn_user_account(
    client: AsyncClient, operator_user: User, operator_token: str, vpn_user_account: User
):
    response = await client.delete(
        f"/api/v1/users/{vpn_user_account.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_operator_cannot_delete_non_vpn_user_account(
    client: AsyncClient, operator_user: User, operator_token: str, viewer_account: User
):
    response = await client.delete(
        f"/api/v1/users/{viewer_account.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_operator_cannot_delete_another_operator(
    client: AsyncClient, operator_user: User, operator_token: str, db_session: AsyncSession
):
    other_operator = User(
        username="operator2",
        hashed_password=hash_password("Operator123!"),
        role="operator",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(other_operator)
    await db_session.flush()

    response = await client.delete(
        f"/api/v1/users/{other_operator.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_still_delete_non_vpn_user_account(
    client: AsyncClient, superuser: User, superuser_token: str, viewer_account: User
):
    response = await client.delete(
        f"/api/v1/users/{viewer_account.id}",
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_viewer_cannot_list_users(client: AsyncClient, db_session: AsyncSession):
    viewer = User(
        username="justviewer",
        hashed_password=hash_password("Whatever123!"),
        role="viewer",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(viewer)
    await db_session.flush()

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "justviewer", "password": "Whatever123!"},
    )
    token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
