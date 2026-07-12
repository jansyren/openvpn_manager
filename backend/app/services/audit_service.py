"""Audit logging.

`record()` writes one AuditLog row per mutation. It is intentionally
best-effort in spirit but called inside the request's DB transaction, so the
audit row commits atomically with the change it describes.
"""
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog


async def record(
    db: AsyncSession,
    *,
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str | int | None = None,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        detail_json=json.dumps(detail) if detail else None,
        ip_address=ip_address,
    )
    db.add(entry)
    await db.flush()
