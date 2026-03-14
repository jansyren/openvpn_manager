import sys

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.db.models.user import User
from app.db.session import get_db
from app.dependencies import get_current_superuser, get_current_user
from app.schemas.system import AuditLogEntry, AuditLogPurgeRequest, HealthCheck, SystemInfo

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", response_model=HealthCheck, include_in_schema=False)
async def health(db: AsyncSession = Depends(get_db)) -> HealthCheck:
    try:
        await db.execute(select(1))  # type: ignore[arg-type]
        db_status = "ok"
    except Exception:
        db_status = "error"
    return HealthCheck(status="ok", database=db_status)


@router.get("/info", response_model=SystemInfo)
async def system_info(_: User = Depends(get_current_user)) -> SystemInfo:
    return SystemInfo(
        app_version="0.1.0",
        openvpn_version=None,  # Could query via executor if a local server is configured
        python_version=sys.version,
        environment="development",
    )


@router.get("/audit-log", response_model=list[AuditLogEntry])
async def get_audit_log(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> list[AuditLogEntry]:
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [AuditLogEntry.model_validate(entry) for entry in result.scalars().all()]


@router.delete("/audit-log", status_code=204)
async def purge_audit_log(
    body: AuditLogPurgeRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> None:
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import delete

    cutoff = datetime.now(UTC) - timedelta(days=body.older_than_days)
    await db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
    await db.flush()
