from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_db
from app.dependencies import get_current_superuser, get_current_user
from app.schemas.server import ServerCreate, ServerRead, ServerTestConnectionResult, ServerUpdate
from app.schemas.vpn_instance import DiscoveredConfig
from app.services import server_service

router = APIRouter(prefix="/servers", tags=["servers"])


@router.get("", response_model=list[ServerRead])
async def list_servers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ServerRead]:
    servers = await server_service.get_servers(db)
    return [ServerRead.from_server(s) for s in servers]


@router.post("", response_model=ServerRead, status_code=201)
async def create_server(
    body: ServerCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> ServerRead:
    server = await server_service.create_server(db, body)
    return ServerRead.from_server(server)


@router.get("/{server_id}", response_model=ServerRead)
async def get_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ServerRead:
    server = await server_service.get_server(db, server_id)
    return ServerRead.from_server(server)


@router.put("/{server_id}", response_model=ServerRead)
async def update_server(
    server_id: int,
    body: ServerUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> ServerRead:
    server = await server_service.update_server(db, server_id, body)
    return ServerRead.from_server(server)


@router.delete("/{server_id}", status_code=204)
async def delete_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> None:
    await server_service.delete_server(db, server_id)


@router.post("/{server_id}/test-connection", response_model=ServerTestConnectionResult)
async def test_connection(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ServerTestConnectionResult:
    result = await server_service.test_connection(db, server_id)
    return ServerTestConnectionResult(**result)


@router.post("/{server_id}/discover", response_model=list[DiscoveredConfig])
async def discover_configs(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[DiscoveredConfig]:
    configs = await server_service.discover_configs(db, server_id)
    return [DiscoveredConfig(**c) for c in configs]
