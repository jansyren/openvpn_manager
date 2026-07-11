"""Authentication service."""
from datetime import UTC, datetime

from sqlalchemy import delete, select
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


async def persist_user_roles(db: AsyncSession, user: User, roles: set[str] | list[str]) -> list[str]:
    """Replace `user`'s rows in user_roles with exactly `roles`, set user.role to the
    highest-priority role among them, and return the roles sorted highest-priority-first.

    `user` must already have a primary key (flushed/inserted).
    """
    from app.db.models.user_role import UserRole
    from app.services.ldap_service import ROLE_PRIORITY, pick_primary_role

    role_set = set(roles) or {"vpn_user"}
    user.role = pick_primary_role(role_set) or "vpn_user"

    await db.execute(delete(UserRole).where(UserRole.user_id == user.id))
    for r in role_set:
        db.add(UserRole(user_id=user.id, role=r))
    await db.flush()

    return sorted(role_set, key=lambda r: ROLE_PRIORITY.get(r, 0), reverse=True)


async def get_available_roles(db: AsyncSession, user: User) -> list[str]:
    """Return user's full resolved role set, highest-priority first.

    Falls back to [user.role] if user_roles has no rows yet (defensive; the
    migration backfill and persist_user_roles should prevent this in practice).
    """
    from app.db.models.user_role import UserRole
    from app.services.ldap_service import ROLE_PRIORITY

    result = await db.execute(select(UserRole.role).where(UserRole.user_id == user.id))
    roles = {r for (r,) in result.all()}
    if not roles:
        return [user.role]
    return sorted(roles, key=lambda r: ROLE_PRIORITY.get(r, 0), reverse=True)


async def authenticate(db: AsyncSession, username: str, password: str) -> User:
    if is_account_locked(username):
        raise AuthError("Account is temporarily locked due to too many failed login attempts")

    result = await db.execute(select(User).where(User.username == username))
    user: User | None = result.scalar_one_or_none()

    if user is not None and user.auth_source == "ldap":
        return await _authenticate_ldap_user(db, user, password)

    if user is None:
        # Try JIT provisioning via any active LDAP config
        ldap_user = await _try_ldap_jit(db, username, password)
        if ldap_user:
            return ldap_user
        locked = record_failed_login(username)
        if locked:
            raise AuthError("Account locked due to too many failed login attempts")
        raise AuthError("Invalid username or password")

    if not verify_password(password, user.hashed_password):
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


async def _authenticate_ldap_user(db: AsyncSession, user: User, password: str) -> User:
    """Verify an existing LDAP user's password via directory bind, and recompute
    their full role set from a fresh memberOf fetch (roles must never go stale)."""
    from app.db.models.ldap_config import LdapConfig
    from app.db.models.ldap_group_mapping import LdapGroupRoleMapping
    from app.services import ldap_service

    if not user.is_active:
        raise ForbiddenError("Account is disabled")

    ldap_cfg: LdapConfig | None = None
    group_dns: list[str] = []
    if user.ldap_config_id:
        result = await db.execute(select(LdapConfig).where(LdapConfig.id == user.ldap_config_id))
        ldap_cfg = result.scalar_one_or_none()

    if ldap_cfg is None:
        # Fall back to trying all active configs
        result = await db.execute(select(LdapConfig).where(LdapConfig.is_active == True))  # noqa: E712
        configs = result.scalars().all()
        for cfg in configs:
            try:
                _user_dn, group_dns = await ldap_service.authenticate_user(cfg, user.username, password)
                ldap_cfg = cfg
                break
            except Exception:
                continue
        if ldap_cfg is None:
            locked = record_failed_login(user.username)
            if locked:
                raise AuthError("Account locked due to too many failed login attempts")
            raise AuthError("Invalid username or password")
    else:
        try:
            _user_dn, group_dns = await ldap_service.authenticate_user(ldap_cfg, user.username, password)
        except Exception:
            locked = record_failed_login(user.username)
            if locked:
                raise AuthError("Account locked due to too many failed login attempts")
            raise AuthError("Invalid username or password")

    mapping_result = await db.execute(
        select(LdapGroupRoleMapping).where(LdapGroupRoleMapping.ldap_config_id == ldap_cfg.id)
    )
    mappings = mapping_result.scalars().all()
    all_roles = ldap_service.determine_all_roles(group_dns, list(mappings))
    await persist_user_roles(db, user, all_roles)

    clear_failed_logins(user.username)
    user.last_login = datetime.now(UTC)
    await db.flush()
    return user


async def _try_ldap_jit(db: AsyncSession, username: str, password: str) -> User | None:
    """Attempt LDAP authentication and JIT-create a User if successful."""
    from app.db.models.ldap_config import LdapConfig
    from app.db.models.ldap_group_mapping import LdapGroupRoleMapping
    from app.services import ldap_service

    result = await db.execute(select(LdapConfig).where(LdapConfig.is_active == True))  # noqa: E712
    configs = result.scalars().all()

    for cfg in configs:
        try:
            user_dn, group_dns = await ldap_service.authenticate_user(cfg, username, password)
        except Exception:
            continue

        # Determine roles from group mappings
        mapping_result = await db.execute(
            select(LdapGroupRoleMapping).where(LdapGroupRoleMapping.ldap_config_id == cfg.id)
        )
        mappings = mapping_result.scalars().all()
        all_roles = ldap_service.determine_all_roles(group_dns, list(mappings))
        primary = ldap_service.pick_primary_role(all_roles) or "vpn_user"

        user = User(
            username=username,
            hashed_password="!ldap",
            auth_source="ldap",
            ldap_dn=user_dn,
            ldap_config_id=cfg.id,
            role=primary,
            is_active=True,
            is_superuser=False,
            last_login=datetime.now(UTC),
        )
        db.add(user)
        await db.flush()  # need user.id before persist_user_roles
        await persist_user_roles(db, user, all_roles)
        clear_failed_logins(username)
        return user

    return None


async def create_tokens(user: User, available_roles: list[str], active_role: str | None = None) -> dict:
    """`available_roles` must be highest-priority-first (as returned by get_available_roles).
    `active_role` defaults to available_roles[0] if None or not a member of available_roles."""
    if active_role not in available_roles:
        active_role = available_roles[0]

    access_token = create_access_token(
        user.id,
        additional_claims={
            "username": user.username,
            "superuser": user.is_superuser,
            "active_role": active_role,
            "roles": available_roles,
        },
    )
    refresh_token, refresh_expires = create_refresh_token(
        user.id,
        additional_claims={"active_role": active_role, "roles": available_roles},
    )
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
    prior_active_role = payload.get("active_role")

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")

    available_roles = await get_available_roles(db, user)
    return await create_tokens(user, available_roles, active_role=prior_active_role)


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
    await persist_user_roles(db, user, {role})
    return user


async def create_initial_superuser(db: AsyncSession, username: str, password: str) -> User:
    """Create the first superuser if no users exist."""
    result = await db.execute(select(User))
    if result.scalars().first() is not None:
        raise AuthError("Users already exist; cannot create initial superuser via this method")

    user = User(
        username=username,
        hashed_password=hash_password(password),
        role="admin",
        is_active=True,
        is_superuser=True,
    )
    db.add(user)
    await db.flush()
    await persist_user_roles(db, user, {"admin"})
    return user
