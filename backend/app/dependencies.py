"""FastAPI dependencies: DB session, auth, executor resolution."""
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import decode_token
from app.db.models.user import User
from app.db.session import get_db
from app.services.auth_service import get_user_by_id

_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    active_role: str


async def get_auth_context(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthContext:
    if credentials is None:
        raise AuthError("No authentication token provided")

    payload = decode_token(credentials.credentials, expected_type="access")
    user_id = int(payload["sub"])
    user = await get_user_by_id(db, user_id)
    active_role = payload.get("active_role") or user.role
    return AuthContext(user=user, active_role=active_role)


async def get_current_user(ctx: AuthContext = Depends(get_auth_context)) -> User:
    return ctx.user


async def get_active_role(ctx: AuthContext = Depends(get_auth_context)) -> str:
    return ctx.active_role


async def get_current_operator(ctx: AuthContext = Depends(get_auth_context)) -> User:
    if not (ctx.user.is_superuser or ctx.active_role in ("admin", "operator")):
        raise ForbiddenError("Operator or admin privileges required")
    return ctx.user


async def get_current_superuser(ctx: AuthContext = Depends(get_auth_context)) -> User:
    if not (ctx.user.is_superuser or ctx.active_role == "admin"):
        raise ForbiddenError("Admin privileges required")
    return ctx.user


def get_client_ip(request: Request) -> str:
    # Respect X-Forwarded-For from reverse proxy
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
