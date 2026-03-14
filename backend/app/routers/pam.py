from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_db
from app.dependencies import get_current_superuser, get_current_user
from app.schemas.pam import PamGroupRead, PamUserCreate, PamUserRead, PamUserUpdate
from app.services import pam_service
from app.services.server_service import get_executor, get_server

router = APIRouter(prefix="/pam", tags=["pam"])


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
    await pam_service.create_user(executor, body.username, body.password, body.groups)
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
    await pam_service.update_user(executor, username, body.password, body.groups)
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
    await pam_service.delete_user(executor, username)


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
