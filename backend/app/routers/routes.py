from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.route import Route
from app.db.models.user import User
from app.db.session import get_db
from app.dependencies import get_current_superuser, get_current_user
from app.schemas.route import LiveRoutingTable, RouteCreate, RouteRead, RouteUpdate
from app.services import route_manager
from app.services.server_service import get_executor, get_server

router = APIRouter(prefix="/routes", tags=["routes"])


@router.get("", response_model=list[RouteRead])
async def list_routes(
    server_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[RouteRead]:
    query = select(Route)
    if server_id is not None:
        query = query.where(Route.server_id == server_id)
    result = await db.execute(query)
    return [RouteRead.model_validate(r) for r in result.scalars().all()]


@router.post("", response_model=RouteRead, status_code=201)
async def create_route(
    body: RouteCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> RouteRead:
    route = Route(**body.model_dump())
    db.add(route)
    await db.flush()
    return RouteRead.model_validate(route)


@router.get("/live/{server_id}", response_model=LiveRoutingTable)
async def get_live_routes(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> LiveRoutingTable:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    routes = await route_manager.get_live_routes(executor)
    return LiveRoutingTable(server_id=server_id, routes=routes)


@router.get("/{route_id}", response_model=RouteRead)
async def get_route(
    route_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RouteRead:
    result = await db.execute(select(Route).where(Route.id == route_id))
    route = result.scalar_one_or_none()
    if route is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Route {route_id} not found")
    return RouteRead.model_validate(route)


@router.put("/{route_id}", response_model=RouteRead)
async def update_route(
    route_id: int,
    body: RouteUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> RouteRead:
    result = await db.execute(select(Route).where(Route.id == route_id))
    route = result.scalar_one_or_none()
    if route is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Route {route_id} not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(route, field, value)
    await db.flush()
    return RouteRead.model_validate(route)


@router.delete("/{route_id}", status_code=204)
async def delete_route(
    route_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> None:
    result = await db.execute(select(Route).where(Route.id == route_id))
    route = result.scalar_one_or_none()
    if route:
        await db.delete(route)
        await db.flush()


@router.post("/{route_id}/apply")
async def apply_route(
    route_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    result = await db.execute(select(Route).where(Route.id == route_id))
    route = result.scalar_one_or_none()
    if route is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Route {route_id} not found")

    server = await get_server(db, route.server_id)
    executor = get_executor(server)
    await route_manager.apply_route(executor, route.destination_network, route.dest_tun, route.metric)
    await route_manager.add_iptables_forward_rule(executor, route.source_tun, route.dest_tun)

    route.is_active = True
    await db.flush()
    return {"message": "Route applied successfully"}


@router.post("/{route_id}/remove")
async def remove_route(
    route_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    result = await db.execute(select(Route).where(Route.id == route_id))
    route = result.scalar_one_or_none()
    if route is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Route {route_id} not found")

    server = await get_server(db, route.server_id)
    executor = get_executor(server)
    await route_manager.remove_route(executor, route.destination_network, route.dest_tun)

    route.is_active = False
    await db.flush()
    return {"message": "Route removed successfully"}
