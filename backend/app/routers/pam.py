from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RemoteExecutionError
from app.db.models.pam import PamGroup, PamUser
from app.db.models.user import User
from app.db.session import get_db
from app.dependencies import get_current_superuser, get_current_user
from app.schemas.pam import (
    PamCopyRequest,
    PamCopyResult,
    PamGroupCreate,
    PamGroupRead,
    PamUserCreate,
    PamUserRead,
    PamUserUpdate,
    StoredPamGroupRead,
    StoredPamUserRead,
)
from app.services import pam_service
from app.services.server_service import get_executor, get_server

router = APIRouter(prefix="/pam", tags=["pam"])


def _use_sudo(server) -> bool:
    return server.sudo_password_encrypted_blob is not None


# ── Stored users (DB) ─────────────────────────────────────────────────────────

@router.get("/users/{server_id}/stored", response_model=list[StoredPamUserRead])
async def list_stored_pam_users(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[StoredPamUserRead]:
    result = await db.execute(select(PamUser).where(PamUser.server_id == server_id))
    rows = result.scalars().all()
    return [
        StoredPamUserRead(
            id=r.id,
            server_id=r.server_id,
            username=r.username,
            groups=r.groups.split(",") if r.groups else [],
            has_hash=bool(r.passwd_hash),
        )
        for r in rows
    ]


# ── Live users (OS) ────────────────────────────────────────────────────────────

@router.get("/users/{server_id}", response_model=list[PamUserRead])
async def list_pam_users(
    server_id: int,
    group: str = "openvpn",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[PamUserRead]:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    users = await pam_service.list_users_in_group(executor, group)
    return [PamUserRead(username=u["username"], groups=[group]) for u in users]


@router.post("/users/{server_id}", response_model=PamUserRead, status_code=201)
async def create_pam_user(
    server_id: int,
    body: PamUserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> PamUserRead:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    use_sudo = _use_sudo(server)
    await pam_service.create_user(executor, body.username, body.password, body.groups, use_sudo=use_sudo)

    # Retrieve shadow hash for storage (non-fatal if unavailable)
    shadow_hash = None
    try:
        shadow_hash = await pam_service.get_user_shadow_hash(executor, body.username, use_sudo=use_sudo)
    except Exception:
        pass

    # Upsert DB record
    existing = await db.execute(
        select(PamUser).where(PamUser.server_id == server_id, PamUser.username == body.username)
    )
    pam_user = existing.scalar_one_or_none()
    if pam_user:
        pam_user.groups = ",".join(body.groups)
        pam_user.passwd_hash = shadow_hash
    else:
        pam_user = PamUser(
            server_id=server_id,
            username=body.username,
            groups=",".join(body.groups),
            passwd_hash=shadow_hash,
        )
        db.add(pam_user)
    await db.flush()

    return PamUserRead(username=body.username, groups=body.groups)


@router.put("/users/{server_id}/{username}", response_model=PamUserRead)
async def update_pam_user(
    server_id: int,
    username: str,
    body: PamUserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> PamUserRead:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    use_sudo = _use_sudo(server)
    await pam_service.update_user(executor, username, body.password, body.groups, use_sudo=use_sudo)

    # Update DB record if it exists
    if body.password or body.groups is not None:
        result = await db.execute(
            select(PamUser).where(PamUser.server_id == server_id, PamUser.username == username)
        )
        pam_user = result.scalar_one_or_none()
        if pam_user:
            if body.groups is not None:
                pam_user.groups = ",".join(body.groups)
            if body.password:
                shadow_hash = None
                try:
                    shadow_hash = await pam_service.get_user_shadow_hash(executor, username, use_sudo=use_sudo)
                except Exception:
                    pass
                if shadow_hash:
                    pam_user.passwd_hash = shadow_hash
            await db.flush()

    return PamUserRead(username=username, groups=body.groups or [])


@router.delete("/users/{server_id}/{username}", status_code=204)
async def delete_pam_user(
    server_id: int,
    username: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> None:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    await pam_service.delete_user(executor, username, use_sudo=_use_sudo(server))
    await db.execute(
        delete(PamUser).where(PamUser.server_id == server_id, PamUser.username == username)
    )


# ── Stored groups (DB) ────────────────────────────────────────────────────────

@router.get("/groups/{server_id}/stored", response_model=list[StoredPamGroupRead])
async def list_stored_pam_groups(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[StoredPamGroupRead]:
    result = await db.execute(select(PamGroup).where(PamGroup.server_id == server_id))
    return [StoredPamGroupRead.model_validate(r) for r in result.scalars().all()]


# ── Live groups (OS) ──────────────────────────────────────────────────────────

@router.get("/groups/{server_id}", response_model=list[PamGroupRead])
async def list_groups(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[PamGroupRead]:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    groups = await pam_service.list_groups(executor)
    return [PamGroupRead(**g) for g in groups]


@router.post("/groups/{server_id}", response_model=StoredPamGroupRead, status_code=201)
async def create_pam_group(
    server_id: int,
    body: PamGroupCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> StoredPamGroupRead:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    await pam_service.create_group(executor, body.name, body.gid, use_sudo=_use_sudo(server))

    # Upsert DB record
    existing = await db.execute(
        select(PamGroup).where(PamGroup.server_id == server_id, PamGroup.name == body.name)
    )
    pam_group = existing.scalar_one_or_none()
    if pam_group:
        pam_group.gid = body.gid
    else:
        pam_group = PamGroup(server_id=server_id, name=body.name, gid=body.gid)
        db.add(pam_group)
    await db.flush()
    await db.refresh(pam_group)
    return StoredPamGroupRead.model_validate(pam_group)


@router.delete("/groups/{server_id}/{name}", status_code=204)
async def delete_pam_group(
    server_id: int,
    name: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> None:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    await pam_service.delete_group(executor, name, use_sudo=_use_sudo(server))
    await db.execute(
        delete(PamGroup).where(PamGroup.server_id == server_id, PamGroup.name == name)
    )


# ── Copy users/groups to another server ──────────────────────────────────────

@router.post("/copy", response_model=PamCopyResult)
async def copy_pam_users(
    body: PamCopyRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> PamCopyResult:
    target = await get_server(db, body.target_server_id)
    # Validate source server exists
    await get_server(db, body.source_server_id)

    target_executor = get_executor(target)
    target_sudo = _use_sudo(target)
    result = PamCopyResult()

    if body.include_groups:
        groups_result = await db.execute(
            select(PamGroup).where(PamGroup.server_id == body.source_server_id)
        )
        for g in groups_result.scalars().all():
            try:
                await pam_service.create_group(target_executor, g.name, g.gid, use_sudo=target_sudo)
                result.groups_created += 1
            except RemoteExecutionError as exc:
                err = str(exc)
                if "exit 9" in err or "already exists" in err:
                    result.groups_skipped += 1
                else:
                    result.groups_failed.append(f"{g.name}: {err}")

    users_result = await db.execute(
        select(PamUser).where(PamUser.server_id == body.source_server_id)
    )
    for u in users_result.scalars().all():
        try:
            groups_list = u.groups.split(",") if u.groups else []
            await pam_service.create_user_with_hash(
                target_executor, u.username, u.passwd_hash, groups_list, use_sudo=target_sudo
            )
            result.users_created += 1
        except RemoteExecutionError as exc:
            err = str(exc)
            if "exit 9" in err or "already exists" in err:
                result.users_skipped += 1
            else:
                result.users_failed.append(f"{u.username}: {err}")

    return result
