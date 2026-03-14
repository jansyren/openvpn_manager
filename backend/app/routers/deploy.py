import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_db
from app.dependencies import get_current_superuser, get_current_user
from app.schemas.system import DeployPrerequisites, DeployRequest, DeployTaskStatus
from app.services import deploy_service
from app.services.server_service import get_executor, get_server

router = APIRouter(prefix="/deploy", tags=["deploy"])


@router.get("/prerequisites/{server_id}", response_model=DeployPrerequisites)
async def check_prerequisites(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DeployPrerequisites:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    info = await deploy_service.check_prerequisites(executor)
    return DeployPrerequisites(server_id=server_id, **info)


@router.post("/{server_id}")
async def start_deployment(
    server_id: int,
    body: DeployRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    server = await get_server(db, server_id)
    executor = get_executor(server)

    task = deploy_service.create_deploy_task()

    asyncio.create_task(
        deploy_service.run_deployment(
            executor,
            task,
            install_openvpn=body.install_openvpn,
            install_easyrsa=body.install_easyrsa,
            openvpn_config_dir=body.openvpn_config_dir,
            easyrsa_install_dir=body.easyrsa_install_dir,
        )
    )

    return {"task_id": task.task_id, "status": "pending"}


@router.get("/status/{task_id}", response_model=DeployTaskStatus)
async def deployment_status(
    task_id: str,
    _: User = Depends(get_current_user),
) -> DeployTaskStatus:
    task = deploy_service.get_deploy_task(task_id)
    if task is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Task {task_id} not found")
    return DeployTaskStatus(
        task_id=task.task_id,
        status=task.status,
        log_lines=task.log_lines,
        error=task.error,
    )


@router.get("/logs/{task_id}")
async def stream_deployment_logs(
    task_id: str,
    _: User = Depends(get_current_user),
) -> StreamingResponse:
    task = deploy_service.get_deploy_task(task_id)
    if task is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Task {task_id} not found")

    async def event_generator():
        while True:
            try:
                line = await asyncio.wait_for(task.log_queue.get(), timeout=30.0)
                yield f"data: {line}\n\n"
                if task.status in ("completed", "failed"):
                    yield "data: [DONE]\n\n"
                    break
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                if task.status in ("completed", "failed"):
                    break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
