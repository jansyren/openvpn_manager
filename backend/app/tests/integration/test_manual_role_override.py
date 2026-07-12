"""Tests for durable manual role overrides that survive LDAP role recomputation.

`persist_user_roles(source=...)` only replaces rows tagged with that source, so an
admin-granted "manual" role survives the next LDAP login's "ldap" recompute instead
of being wiped out by it.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.user import User
from app.services.auth_service import get_available_roles, persist_user_roles


@pytest.mark.asyncio
async def test_manual_override_survives_ldap_recompute(db_session: AsyncSession):
    user = User(
        username="ldapuser",
        hashed_password=hash_password("Whatever123!"),
        auth_source="ldap",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()

    # Admin manually grants "admin" via the Users page.
    await persist_user_roles(db_session, user, {"admin"}, source="manual")
    assert set(await get_available_roles(db_session, user)) == {"admin"}

    # User's next LDAP login resolves them to "vpn_user" only from their AD groups.
    merged = await persist_user_roles(db_session, user, {"vpn_user"}, source="ldap")
    assert set(merged) == {"admin", "vpn_user"}
    assert user.role == "admin"  # highest-priority role across both sources


@pytest.mark.asyncio
async def test_ldap_recompute_only_replaces_its_own_rows(db_session: AsyncSession):
    user = User(
        username="ldapuser2",
        hashed_password=hash_password("Whatever123!"),
        auth_source="ldap",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()

    await persist_user_roles(db_session, user, {"admin"}, source="manual")
    await persist_user_roles(db_session, user, {"vpn_user"}, source="ldap")

    # AD group membership changes: now resolves to "operator" instead of "vpn_user".
    merged = await persist_user_roles(db_session, user, {"operator"}, source="ldap")
    assert set(merged) == {"admin", "operator"}  # manual "admin" untouched, ldap role updated


@pytest.mark.asyncio
async def test_manual_recompute_only_replaces_its_own_rows(db_session: AsyncSession):
    user = User(
        username="ldapuser3",
        hashed_password=hash_password("Whatever123!"),
        auth_source="ldap",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()

    await persist_user_roles(db_session, user, {"vpn_user"}, source="ldap")
    await persist_user_roles(db_session, user, {"admin"}, source="manual")

    # Admin later changes the manual override to "viewer" instead of "admin".
    merged = await persist_user_roles(db_session, user, {"viewer"}, source="manual")
    assert set(merged) == {"viewer", "vpn_user"}  # ldap "vpn_user" untouched
