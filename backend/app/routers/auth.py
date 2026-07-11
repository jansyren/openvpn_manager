from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import blacklist_token, decode_token
from app.db.session import get_db
from app.dependencies import get_active_role, get_client_ip, get_current_user
from app.db.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    SwitchRoleRequest,
    TokenResponse,
    UserRead,
)
from app.services.auth_service import (
    authenticate,
    change_password,
    create_tokens,
    get_available_roles,
    refresh_access_token,
)

from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"
_COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 days


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = await authenticate(db, body.username, body.password)
    available_roles = await get_available_roles(db, user)
    tokens = await create_tokens(user, available_roles)

    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=tokens["refresh_token"],
        httponly=True,
        secure=get_settings().is_production,
        samesite="strict",
        max_age=_COOKIE_MAX_AGE,
        path="/api/v1/auth",
    )

    return TokenResponse(
        access_token=tokens["access_token"],
        expires_in=tokens["expires_in"],
    )


@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    # Blacklist the current access token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = decode_token(token)
            jti = payload.get("jti", "")
            exp = datetime.fromtimestamp(payload.get("exp", 0), tz=UTC)
            blacklist_token(jti, exp)
        except Exception:
            pass

    response.delete_cookie(_REFRESH_COOKIE, path="/api/v1/auth", secure=get_settings().is_production)
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    refresh_token = request.cookies.get(_REFRESH_COOKIE)
    if not refresh_token:
        from app.core.exceptions import AuthError
        raise AuthError("No refresh token")

    tokens = await refresh_access_token(db, refresh_token)

    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=tokens["refresh_token"],
        httponly=True,
        secure=get_settings().is_production,
        samesite="strict",
        max_age=_COOKIE_MAX_AGE,
        path="/api/v1/auth",
    )

    return TokenResponse(
        access_token=tokens["access_token"],
        expires_in=tokens["expires_in"],
    )


@router.get("/me", response_model=UserRead)
async def me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    active_role: str = Depends(get_active_role),
) -> UserRead:
    roles = await get_available_roles(db, current_user)
    return UserRead(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        roles=roles,
        active_role=active_role,
    )


@router.post("/switch-role", response_model=TokenResponse)
async def switch_role(
    body: SwitchRoleRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TokenResponse:
    from app.core.exceptions import ForbiddenError

    available_roles = await get_available_roles(db, current_user)
    if body.role not in available_roles:
        raise ForbiddenError(f"Role '{body.role}' is not available to this user")

    tokens = await create_tokens(current_user, available_roles, active_role=body.role)

    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=tokens["refresh_token"],
        httponly=True,
        secure=get_settings().is_production,
        samesite="strict",
        max_age=_COOKIE_MAX_AGE,
        path="/api/v1/auth",
    )

    return TokenResponse(
        access_token=tokens["access_token"],
        expires_in=tokens["expires_in"],
    )


@router.put("/me/password")
async def change_my_password(
    body: ChangePasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    from datetime import UTC, datetime

    auth_header = request.headers.get("Authorization", "")
    jti = ""
    exp = datetime.now(UTC)
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = decode_token(token)
            jti = payload.get("jti", "")
            exp = datetime.fromtimestamp(payload.get("exp", 0), tz=UTC)
        except Exception:
            pass

    await change_password(db, current_user, body.current_password, body.new_password, jti, exp)
    return {"message": "Password changed successfully"}
