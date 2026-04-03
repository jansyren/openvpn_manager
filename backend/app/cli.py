"""
Management CLI — run with:
    uv run python -m app.cli create-admin
    uv run python -m app.cli ensure-admin   (uses APP_ADMIN_USERNAME / APP_ADMIN_PASSWORD env vars)
"""
import asyncio
import getpass
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models.user import User
from app.db.session import get_session_factory


async def _create_admin(username: str, password: str) -> None:
    async with get_session_factory()() as session:
        existing = await session.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none():
            print(f"Admin '{username}' already exists, skipping.")
            return

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


def ensure_admin() -> None:
    """Create admin from APP_ADMIN_USERNAME / APP_ADMIN_PASSWORD env vars if set."""
    from app.config import get_settings

    settings = get_settings()
    if not settings.app_admin_username or not settings.app_admin_password:
        return
    if len(settings.app_admin_password) < 12:
        print("APP_ADMIN_PASSWORD must be at least 12 characters.")
        sys.exit(1)

    asyncio.run(_create_admin(settings.app_admin_username, settings.app_admin_password))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.cli <create-admin|ensure-admin>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "create-admin":
        create_admin()
    elif cmd == "ensure-admin":
        ensure_admin()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
