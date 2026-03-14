"""FastAPI dependencies: DB session, auth, executor resolution."""
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import decode_token
from app.db.models.user import User
from app.db.session import get_db
from app.services.auth_service import get_user_by_id

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    if credentials is None:
        raise AuthError("No authentication token provided")

    payload = decode_token(credentials.credentials, expected_type="access")
    user_id = int(payload["sub"])
    return await get_user_by_id(db, user_id)


async def get_current_operator(
    current_user: User = Depends(get_current_user),
) -> User:
    if not (current_user.is_superuser or current_user.role in ("admin", "operator")):
        raise ForbiddenError("Operator or admin privileges required")
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not (current_user.is_superuser or current_user.role == "admin"):
        raise ForbiddenError("Admin privileges required")
    return current_user


def get_client_ip(request: Request) -> str:
    # Respect X-Forwarded-For from reverse proxy
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
