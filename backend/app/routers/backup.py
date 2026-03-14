from pathlib import PurePosixPath

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.backup import Backup
from app.db.models.user import User
from app.db.models.vpn_instance import VpnInstance
from app.db.session import get_db
from app.dependencies import get_current_superuser, get_current_user
from app.schemas.backup import BackupCreate, BackupRead, RestoreRequest
from app.services import backup_service
from app.services.server_service import get_executor, get_server

router = APIRouter(prefix="/backup", tags=["backup"])


@router.get("", response_model=list[BackupRead])
async def list_backups(
    server_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[BackupRead]:
    query = select(Backup).order_by(Backup.created_at.desc())
    if server_id is not None:
        query = query.where(Backup.server_id == server_id)
    result = await db.execute(query)
    return [BackupRead.model_validate(b) for b in result.scalars().all()]


@router.post("", response_model=BackupRead, status_code=201)
async def create_backup(
    body: BackupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> BackupRead:
    instance = None
    if body.vpn_instance_id is not None:
        inst_result = await db.execute(
            select(VpnInstance).where(VpnInstance.id == body.vpn_instance_id)
        )
        instance = inst_result.scalar_one_or_none()

    # Validate the VPN server exists and get its name for the backup filename
    vpn_server = await get_server(db, body.server_id)

    # For easyrsa backups, run tar on the server where easy-rsa actually lives
    backup_server_id = body.server_id
    if instance is not None and body.backup_type in ("full", "easyrsa"):
        backup_server_id = instance.easyrsa_server_id or body.server_id
    backup_server = await get_server(db, backup_server_id)
    executor = get_executor(backup_server)

    source_paths = []
    if body.backup_type in ("full", "server_config"):
        source_paths.append("/etc/openvpn")
    if body.backup_type in ("full", "easyrsa"):
        if instance is not None:
            if instance.pki_dir:
                easyrsa_backup_path = instance.pki_dir
            elif instance.easyrsa_path:
                # Derive parent directory from binary path (e.g. /usr/share/easy-rsa/easyrsa → /usr/share/easy-rsa)
                easyrsa_backup_path = str(PurePosixPath(instance.easyrsa_path).parent)
            else:
                easyrsa_backup_path = "/etc/easy-rsa"
            source_paths.append(easyrsa_backup_path)
        else:
            source_paths.append("/etc/easy-rsa")

    filename, _, sha256 = await backup_service.create_backup(
        executor, source_paths, body.backup_type, vpn_server.name
    )
    from app.config import get_settings
    settings = get_settings()
    storage_path = str(settings.backup_storage_path / filename)

    import os
    size_bytes = os.path.getsize(storage_path)

    backup = Backup(
        server_id=body.server_id,
        filename=filename,
        size_bytes=size_bytes,
        sha256=sha256,
        backup_type=body.backup_type,
        storage_path=storage_path,
        notes=body.notes,
        created_by=current_user.id,
    )
    db.add(backup)
    await db.flush()
    return BackupRead.model_validate(backup)


@router.get("/{backup_id}", response_model=BackupRead)
async def get_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> BackupRead:
    result = await db.execute(select(Backup).where(Backup.id == backup_id))
    backup = result.scalar_one_or_none()
    if backup is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Backup {backup_id} not found")
    return BackupRead.model_validate(backup)


@router.get("/{backup_id}/download")
async def download_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> FileResponse:
    result = await db.execute(select(Backup).where(Backup.id == backup_id))
    backup = result.scalar_one_or_none()
    if backup is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Backup {backup_id} not found")

    return FileResponse(
        path=backup.storage_path,
        filename=backup.filename,
        media_type="application/gzip",
    )


@router.post("/{backup_id}/restore")
async def restore_backup(
    backup_id: int,
    body: RestoreRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    result = await db.execute(select(Backup).where(Backup.id == backup_id))
    backup = result.scalar_one_or_none()
    if backup is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Backup {backup_id} not found")

    if backup.server_id is None:
        from app.core.exceptions import ValidationError
        raise ValidationError("Backup has no associated server")

    server = await get_server(db, backup.server_id)
    executor = get_executor(server)

    await backup_service.restore_backup(
        backup.storage_path,
        body.expected_sha256,
        executor,
        create_snapshot=body.create_pre_restore_snapshot,
    )
    return {"message": "Backup restored successfully"}


@router.delete("/{backup_id}", status_code=204)
async def delete_backup(
    backup_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> None:
    result = await db.execute(select(Backup).where(Backup.id == backup_id))
    backup = result.scalar_one_or_none()
    if backup:
        import os
        try:
            os.unlink(backup.storage_path)
        except OSError:
            pass
        await db.delete(backup)
        await db.flush()
