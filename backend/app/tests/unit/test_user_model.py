"""Tests for the User model's role default (SEC-1 / B4).

A user constructed without an explicit role must default to the lowest-privilege
role, never admin — silently minting an admin is a privilege-escalation footgun.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models.user import User


@pytest.mark.asyncio
async def test_user_without_role_defaults_to_least_privilege(db_session: AsyncSession):
    user = User(
        username="norole",
        hashed_password=hash_password("Whatever123!"),
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    assert user.role != "admin"
    assert user.role == "vpn_user"
