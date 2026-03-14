"""
Management CLI — run with:
    uv run python -m app.cli create-admin
"""
import asyncio
import getpass
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_engine, get_session_factory


async def _ensure_tables() -> None:
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _create_admin(username: str, password: str) -> None:
    await _ensure_tables()
    async with get_session_factory()() as session:
        existing = await session.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none():
            print(f"User '{username}' already exists.")
            sys.exit(1)

        user = User(
            username=username,
            hashed_password=hash_password(password),
            is_active=True,
            is_superuser=True,
        )
        session.add(user)
        await session.commit()
        print(f"Superuser '{username}' created successfully.")


def create_admin() -> None:
    username = input("Admin username: ").strip()
    if not username:
        print("Username cannot be empty.")
        sys.exit(1)

    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        sys.exit(1)
    if len(password) < 12:
        print("Password must be at least 12 characters.")
        sys.exit(1)

    asyncio.run(_create_admin(username, password))


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] != "create-admin":
        print("Usage: python -m app.cli create-admin")
        sys.exit(1)
    create_admin()
