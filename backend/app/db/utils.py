"""Small shared DB helpers."""
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


async def get_or_404(
    db: AsyncSession, model: type[ModelT], obj_id: int, name: str | None = None
) -> ModelT:
    """Fetch a row by primary key `obj_id` or raise NotFoundError.

    `name` overrides the label used in the error message (defaults to the model
    class name), so callers can preserve human-friendly messages like
    "VPN instance 5 not found".
    """
    result = await db.execute(select(model).where(model.id == obj_id))  # type: ignore[attr-defined]
    obj = result.scalar_one_or_none()
    if obj is None:
        raise NotFoundError(f"{name or model.__name__} {obj_id} not found")
    return obj
