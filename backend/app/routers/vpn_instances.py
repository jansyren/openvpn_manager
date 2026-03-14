from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.models.vpn_instance import VpnInstance
from app.db.session import get_db
from app.dependencies import get_current_superuser, get_current_user
from app.schemas.vpn_instance import (
    DiscoveredConfig,
    ServiceActionRequest,
    VpnInstanceCreate,
    VpnInstanceRead,
    VpnInstanceStatus,
    VpnInstanceUpdate,
)
from app.services.config_parser import ParsedConfig, parse_config, serialize_config
from app.services.openvpn_directives import DirectiveSpec, get_all_directives
from app.services.server_service import get_executor, get_server
from app.services.service_manager import get_service_logs, get_service_status, service_action

router = APIRouter(prefix="/vpn-instances", tags=["vpn-instances"])


@router.get("", response_model=list[VpnInstanceRead])
async def list_instances(
    server_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[VpnInstanceRead]:
    query = select(VpnInstance)
    if server_id is not None:
        query = query.where(VpnInstance.server_id == server_id)
    result = await db.execute(query.order_by(VpnInstance.name))
    return [VpnInstanceRead.model_validate(i) for i in result.scalars().all()]


@router.post("", response_model=VpnInstanceRead, status_code=201)
async def create_instance(
    body: VpnInstanceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> VpnInstanceRead:
    instance = VpnInstance(**body.model_dump())
    db.add(instance)
    await db.flush()
    return VpnInstanceRead.model_validate(instance)


@router.get("/directives", response_model=list[DirectiveSpec])
async def list_directives(_: User = Depends(get_current_user)) -> list[DirectiveSpec]:
    return get_all_directives()


@router.get("/{instance_id}", response_model=VpnInstanceRead)
async def get_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> VpnInstanceRead:
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"VPN instance {instance_id} not found")
    return VpnInstanceRead.model_validate(instance)


@router.put("/{instance_id}", response_model=VpnInstanceRead)
async def update_instance(
    instance_id: int,
    body: VpnInstanceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> VpnInstanceRead:
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"VPN instance {instance_id} not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(instance, field, value)
    await db.flush()
    return VpnInstanceRead.model_validate(instance)


@router.delete("/{instance_id}", status_code=204)
async def delete_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> None:
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance:
        await db.delete(instance)
        await db.flush()


@router.get("/{instance_id}/config")
async def read_config(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"VPN instance {instance_id} not found")

    server = await get_server(db, instance.server_id)
    executor = get_executor(server)
    content_bytes = await executor.read_file(instance.config_path)
    parsed = parse_config(content_bytes.decode("utf-8", errors="replace"))
    return {"directives": parsed.directives, "inline_blocks": list(parsed.inline_blocks.keys())}


@router.put("/{instance_id}/config")
async def write_config(
    instance_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"VPN instance {instance_id} not found")

    server = await get_server(db, instance.server_id)
    executor = get_executor(server)

    parsed = ParsedConfig(directives=body.get("directives", {}))
    content = serialize_config(parsed)
    await executor.write_file(instance.config_path, content.encode(), mode=0o640)
    return {"message": "Config written successfully"}


@router.post("/{instance_id}/service")
async def control_service(
    instance_id: int,
    body: ServiceActionRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"VPN instance {instance_id} not found")

    server = await get_server(db, instance.server_id)
    executor = get_executor(server)
    return await service_action(executor, instance.name, body.action)


@router.get("/{instance_id}/status", response_model=VpnInstanceStatus)
async def get_status(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> VpnInstanceStatus:
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"VPN instance {instance_id} not found")

    server = await get_server(db, instance.server_id)
    executor = get_executor(server)
    status_info = await get_service_status(executor, instance.name)

    instance.status = status_info["status"]
    await db.flush()

    return VpnInstanceStatus(
        instance_id=instance_id,
        name=instance.name,
        **status_info,
    )


@router.get("/{instance_id}/logs")
async def get_logs(
    instance_id: int,
    lines: int = Query(100, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"VPN instance {instance_id} not found")

    server = await get_server(db, instance.server_id)
    executor = get_executor(server)
    logs = await get_service_logs(executor, instance.name, lines=lines)
    return {"logs": logs}
