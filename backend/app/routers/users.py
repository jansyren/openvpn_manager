"""User management router (admin only)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.db.models.user import User
from app.db.session import get_db
from app.dependencies import get_current_superuser
from app.schemas.user_management import UserCreate, UserManagementRead, UserUpdate
from app.services.auth_service import create_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserManagementRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> list[UserManagementRead]:
    result = await db.execute(select(User).order_by(User.id))
    return [UserManagementRead.model_validate(u) for u in result.scalars().all()]


@router.post("", response_model=UserManagementRead, status_code=201)
async def create_user_endpoint(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> UserManagementRead:
    user = await create_user(db, body.username, body.password, body.role, body.is_active)
    return UserManagementRead.model_validate(user)


@router.get("/{user_id}", response_model=UserManagementRead)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> UserManagementRead:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    return UserManagementRead.model_validate(user)


@router.put("/{user_id}", response_model=UserManagementRead)
async def update_user(
    user_id: int,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> UserManagementRead:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError(f"User {user_id} not found")

    if body.role is not None and user.id == current_user.id:
        raise ForbiddenError("Cannot modify your own role")

    if body.password is not None:
        user.hashed_password = hash_password(body.password)
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active

    await db.flush()
    return UserManagementRead.model_validate(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> None:
    if user_id == current_user.id:
        raise ForbiddenError("Cannot delete your own account")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError(f"User {user_id} not found")

    await db.delete(user)
    await db.flush()
