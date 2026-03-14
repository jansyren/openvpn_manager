"""Authentication service."""
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import (
    blacklist_token,
    clear_failed_logins,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_account_locked,
    record_failed_login,
    verify_password,
)
from app.db.models.user import User


async def authenticate(db: AsyncSession, username: str, password: str) -> User:
    if is_account_locked(username):
        raise AuthError("Account is temporarily locked due to too many failed login attempts")

    result = await db.execute(select(User).where(User.username == username))
    user: User | None = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.hashed_password):
        locked = record_failed_login(username)
        if locked:
            raise AuthError("Account locked due to too many failed login attempts")
        raise AuthError("Invalid username or password")

    if not user.is_active:
        raise ForbiddenError("Account is disabled")

    clear_failed_logins(username)
    user.last_login = datetime.now(UTC)
    await db.flush()
    return user


async def create_tokens(user: User) -> dict:
    access_token = create_access_token(
        user.id,
        additional_claims={"username": user.username, "superuser": user.is_superuser},
    )
    refresh_token, refresh_expires = create_refresh_token(user.id)
    from app.config import get_settings

    settings = get_settings()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "refresh_expires": refresh_expires,
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> dict:
    payload = decode_token(refresh_token, expected_type="refresh")
    user_id = int(payload["sub"])

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")

    return await create_tokens(user)


async def get_user_by_id(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()
    if user is None:
        raise AuthError("User not found")
    return user


async def change_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
    current_token_jti: str,
    current_token_exp: datetime,
) -> None:
    if not verify_password(current_password, user.hashed_password):
        raise AuthError("Current password is incorrect")

    user.hashed_password = hash_password(new_password)
    await db.flush()

    # Invalidate the current token
    blacklist_token(current_token_jti, current_token_exp)


async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
    role: str = "viewer",
    is_active: bool = True,
) -> User:
    """Create a new user with the given credentials and role."""
    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none() is not None:
        from app.core.exceptions import ValidationError
        raise ValidationError(f"Username '{username}' is already taken")

    user = User(
        username=username,
        hashed_password=hash_password(password),
        role=role,
        is_active=is_active,
        is_superuser=False,
    )
    db.add(user)
    await db.flush()
    return user


async def create_initial_superuser(db: AsyncSession, username: str, password: str) -> User:
    """Create the first superuser if no users exist."""
    result = await db.execute(select(User))
    if result.scalars().first() is not None:
        raise AuthError("Users already exist; cannot create initial superuser via this method")

    user = User(
        username=username,
        hashed_password=hash_password(password),
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    await db.flush()
    return user
