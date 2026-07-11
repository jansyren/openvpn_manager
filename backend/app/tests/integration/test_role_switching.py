"""Integration tests for multi-role users and the /auth/switch-role flow."""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.server import Server
from app.db.models.user import User
from app.db.models.user_role import UserRole
from app.db.models.vpn_client import VpnClient
from app.db.models.vpn_instance import VpnInstance


@pytest_asyncio.fixture
async def dual_role_user(db_session: AsyncSession) -> User:
    """Simulates a dual-role LDAP-provisioned user without needing a live LDAP server:
    a user whose resolved role set is {"admin", "vpn_user"}, primary role "admin"."""
    user = User(
        username="dualrole",
        hashed_password=hash_password("DualRole123!"),
        is_active=True,
        is_superuser=False,
        role="admin",
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(UserRole(user_id=user.id, role="admin"))
    db_session.add(UserRole(user_id=user.id, role="vpn_user"))
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def dual_role_token(client: AsyncClient, dual_role_user: User) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "dualrole", "password": "DualRole123!"},
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_me_shows_full_role_set_and_default_active_role(
    client: AsyncClient, dual_role_user: User, dual_role_token: str
):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {dual_role_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert set(data["roles"]) == {"admin", "vpn_user"}
    # admin outranks vpn_user, so it's the default active role at login
    assert data["active_role"] == "admin"


@pytest.mark.asyncio
async def test_switch_role_to_vpn_user(client: AsyncClient, dual_role_user: User, dual_role_token: str):
    response = await client.post(
        "/api/v1/auth/switch-role",
        headers={"Authorization": f"Bearer {dual_role_token}"},
        json={"role": "vpn_user"},
    )
    assert response.status_code == 200
    new_token = response.json()["access_token"]

    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert me_response.json()["active_role"] == "vpn_user"


@pytest.mark.asyncio
async def test_switch_role_to_unavailable_role_is_forbidden(
    client: AsyncClient, dual_role_user: User, dual_role_token: str
):
    response = await client.post(
        "/api/v1/auth/switch-role",
        headers={"Authorization": f"Bearer {dual_role_token}"},
        json={"role": "operator"},
    )
    assert response.status_code == 403


@pytest_asyncio.fixture
async def vpn_clients(db_session: AsyncSession, dual_role_user: User) -> tuple[VpnClient, VpnClient]:
    server = Server(name="test-server", is_local=True)
    db_session.add(server)
    await db_session.flush()

    instance = VpnInstance(server_id=server.id, name="test-instance", config_path="/etc/openvpn/server.conf")
    db_session.add(instance)
    await db_session.flush()

    own_client = VpnClient(vpn_instance_id=instance.id, name=dual_role_user.username, client_type="user")
    other_client = VpnClient(vpn_instance_id=instance.id, name="someone-else", client_type="user")
    db_session.add(own_client)
    db_session.add(other_client)
    await db_session.flush()
    return own_client, other_client


@pytest.mark.asyncio
async def test_clients_list_filtered_when_active_role_is_vpn_user(
    client: AsyncClient, dual_role_user: User, dual_role_token: str, vpn_clients
):
    switch_response = await client.post(
        "/api/v1/auth/switch-role",
        headers={"Authorization": f"Bearer {dual_role_token}"},
        json={"role": "vpn_user"},
    )
    vpn_user_token = switch_response.json()["access_token"]

    response = await client.get(
        "/api/v1/clients",
        headers={"Authorization": f"Bearer {vpn_user_token}"},
    )
    assert response.status_code == 200
    names = {c["name"] for c in response.json()}
    assert names == {dual_role_user.username}


@pytest.mark.asyncio
async def test_clients_list_unfiltered_when_active_role_is_admin(
    client: AsyncClient, dual_role_user: User, dual_role_token: str, vpn_clients
):
    response = await client.get(
        "/api/v1/clients",
        headers={"Authorization": f"Bearer {dual_role_token}"},
    )
    assert response.status_code == 200
    names = {c["name"] for c in response.json()}
    assert names == {dual_role_user.username, "someone-else"}


@pytest.mark.asyncio
async def test_refresh_preserves_switched_active_role(
    client: AsyncClient, dual_role_user: User, dual_role_token: str
):
    """The single most important regression test: the axios interceptor silently
    calls /auth/refresh on 401. If refresh reset active_role to the default, a
    user's deliberate role switch would revert a few minutes later."""
    switch_response = await client.post(
        "/api/v1/auth/switch-role",
        headers={"Authorization": f"Bearer {dual_role_token}"},
        json={"role": "vpn_user"},
    )
    assert switch_response.status_code == 200

    refresh_response = await client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 200
    refreshed_token = refresh_response.json()["access_token"]

    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refreshed_token}"},
    )
    assert me_response.json()["active_role"] == "vpn_user"
