from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.models.vpn_instance import VpnInstance
from app.db.session import get_db
from app.dependencies import get_current_superuser, get_current_user
from app.schemas.easyrsa import (
    EasyRsaBuildCa,
    EasyRsaBuildServer,
    EasyRsaCrossSign,
    EasyRsaInitPki,
    EasyRsaPathUpdate,
    EasyRsaPkiDirUpdate,
    EasyRsaRenewCa,
    EasyRsaServerUpdate,
    EasyRsaSettings,
    EasyRsaSudoUpdate,
    ServerBuildCa,
    ServerBuildServerCert,
    ServerCrossSign,
    ServerGenDh,
    ServerInitPki,
    ServerPkiStatusRequest,
    ServerRenewCa,
)
from app.services import easyrsa_service
from app.services.server_service import get_executor, get_server

router = APIRouter(prefix="/easyrsa", tags=["easyrsa"])

_DEFAULT_PKI_DIR = "/etc/easy-rsa/pki"


async def _get_instance(instance_id: int, db: AsyncSession) -> VpnInstance:
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"VPN instance {instance_id} not found")
    return instance


async def _get_easyrsa_executor(instance: VpnInstance, db: AsyncSession):
    server_id = instance.easyrsa_server_id if instance.easyrsa_server_id is not None else instance.server_id
    server = await get_server(db, server_id)
    return get_executor(server)


def _resolve_pki_dir(instance: VpnInstance) -> str:
    return instance.pki_dir or _DEFAULT_PKI_DIR


@router.get("/{vpn_instance_id}/settings", response_model=EasyRsaSettings)
async def get_settings(
    vpn_instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> EasyRsaSettings:
    instance = await _get_instance(vpn_instance_id, db)
    pki_dir = _resolve_pki_dir(instance)
    executor = await _get_easyrsa_executor(instance, db)
    status = await easyrsa_service.pki_status(executor, pki_dir)
    return EasyRsaSettings(
        easyrsa_path=instance.easyrsa_path,
        pki_dir=instance.pki_dir,
        easyrsa_server_id=instance.easyrsa_server_id,
        easyrsa_use_sudo=instance.easyrsa_use_sudo,
        pki_initialized=status["pki_initialized"],
        ca_built=status["ca_built"],
        permission_error=status.get("permission_error", False),
        error_detail=status.get("error_detail"),
    )


@router.put("/{vpn_instance_id}/path")
async def update_path(
    vpn_instance_id: int,
    body: EasyRsaPathUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    instance = await _get_instance(vpn_instance_id, db)
    instance.easyrsa_path = body.easyrsa_path
    await db.flush()
    return {"message": "easy-rsa path updated", "easyrsa_path": body.easyrsa_path}


@router.put("/{vpn_instance_id}/pki-dir")
async def update_pki_dir(
    vpn_instance_id: int,
    body: EasyRsaPkiDirUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    instance = await _get_instance(vpn_instance_id, db)
    instance.pki_dir = body.pki_dir
    await db.flush()
    return {"message": "PKI directory updated", "pki_dir": body.pki_dir}


@router.put("/{vpn_instance_id}/sudo")
async def update_sudo(
    vpn_instance_id: int,
    body: EasyRsaSudoUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    instance = await _get_instance(vpn_instance_id, db)
    instance.easyrsa_use_sudo = body.easyrsa_use_sudo
    await db.flush()
    return {"message": "sudo setting updated", "easyrsa_use_sudo": body.easyrsa_use_sudo}


@router.put("/{vpn_instance_id}/server")
async def update_easyrsa_server(
    vpn_instance_id: int,
    body: EasyRsaServerUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    instance = await _get_instance(vpn_instance_id, db)
    instance.easyrsa_server_id = body.easyrsa_server_id
    await db.flush()
    return {"message": "easy-rsa server updated", "easyrsa_server_id": body.easyrsa_server_id}


@router.post("/{vpn_instance_id}/init-pki")
async def init_pki(
    vpn_instance_id: int,
    body: EasyRsaInitPki,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    instance = await _get_instance(vpn_instance_id, db)
    easyrsa_path = instance.easyrsa_path or easyrsa_service.DEFAULT_EASYRSA_PATH
    pki_dir = _resolve_pki_dir(instance)
    executor = await _get_easyrsa_executor(instance, db)
    output = await easyrsa_service.init_pki(executor, easyrsa_path, pki_dir, body.force, use_sudo=instance.easyrsa_use_sudo)
    return {"message": "PKI initialised", "output": output}


@router.post("/{vpn_instance_id}/build-ca")
async def build_ca(
    vpn_instance_id: int,
    body: EasyRsaBuildCa,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    instance = await _get_instance(vpn_instance_id, db)
    easyrsa_path = instance.easyrsa_path or easyrsa_service.DEFAULT_EASYRSA_PATH
    pki_dir = _resolve_pki_dir(instance)
    executor = await _get_easyrsa_executor(instance, db)
    output = await easyrsa_service.build_ca(
        executor, easyrsa_path, pki_dir, body.common_name, body.passphrase, body.expire_days,
        use_sudo=instance.easyrsa_use_sudo,
    )
    return {"message": "CA built successfully", "output": output}


@router.post("/{vpn_instance_id}/build-server")
async def build_server(
    vpn_instance_id: int,
    body: EasyRsaBuildServer,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    instance = await _get_instance(vpn_instance_id, db)
    easyrsa_path = instance.easyrsa_path or easyrsa_service.DEFAULT_EASYRSA_PATH
    pki_dir = _resolve_pki_dir(instance)
    executor = await _get_easyrsa_executor(instance, db)
    output = await easyrsa_service.build_server_full(
        executor, easyrsa_path, pki_dir, body.common_name, body.passphrase or "", body.expire_days,
        use_sudo=instance.easyrsa_use_sudo,
    )
    return {"message": "Server certificate built", "output": output}


@router.post("/{vpn_instance_id}/gen-dh")
async def gen_dh(
    vpn_instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    instance = await _get_instance(vpn_instance_id, db)
    easyrsa_path = instance.easyrsa_path or easyrsa_service.DEFAULT_EASYRSA_PATH
    pki_dir = _resolve_pki_dir(instance)
    executor = await _get_easyrsa_executor(instance, db)
    output = await easyrsa_service.gen_dh(executor, easyrsa_path, pki_dir, use_sudo=instance.easyrsa_use_sudo)
    return {"message": "DH parameters generated", "output": output}


@router.get("/{vpn_instance_id}/pki-status")
async def pki_status(
    vpn_instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    instance = await _get_instance(vpn_instance_id, db)
    pki_dir = _resolve_pki_dir(instance)
    executor = await _get_easyrsa_executor(instance, db)
    return await easyrsa_service.pki_status(executor, pki_dir)


@router.post("/{vpn_instance_id}/renew-ca")
async def renew_ca(
    vpn_instance_id: int,
    body: EasyRsaRenewCa,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Renew the self-signed CA certificate (same key, new expiry). Uses OpenSSL."""
    from app.core.security import decrypt_ca_passphrase

    instance = await _get_instance(vpn_instance_id, db)
    pki_dir = _resolve_pki_dir(instance)
    executor = await _get_easyrsa_executor(instance, db)

    ca_passphrase = body.ca_passphrase
    if not ca_passphrase and instance.ca_passphrase_encrypted_blob:
        ca_passphrase = decrypt_ca_passphrase(instance.ca_passphrase_encrypted_blob)

    await easyrsa_service.renew_ca(executor, pki_dir, ca_passphrase or "", body.expire_days)
    return {"message": f"CA certificate renewed for {body.expire_days} days", "pki_dir": pki_dir}


@router.post("/{vpn_instance_id}/cross-sign")
async def cross_sign(
    vpn_instance_id: int,
    body: EasyRsaCrossSign,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Cross-sign a new CA's CSR with this instance's old CA key."""
    from app.core.security import decrypt_ca_passphrase

    instance = await _get_instance(vpn_instance_id, db)
    pki_dir = _resolve_pki_dir(instance)
    executor = await _get_easyrsa_executor(instance, db)

    old_ca_passphrase = body.old_ca_passphrase
    if not old_ca_passphrase and instance.ca_passphrase_encrypted_blob:
        old_ca_passphrase = decrypt_ca_passphrase(instance.ca_passphrase_encrypted_blob)

    cross_cert_pem = await easyrsa_service.cross_sign_ca(
        executor, pki_dir, body.new_ca_csr_pem, old_ca_passphrase or "", body.expire_days
    )
    return {"message": "Cross-signed certificate generated", "cross_cert_pem": cross_cert_pem}


# ── Server-level Easy-RSA routes (no VPN instance required) ─────────────


@router.post("/server/{server_id}/pki-status")
async def server_pki_status(
    server_id: int,
    body: ServerPkiStatusRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    status = await easyrsa_service.pki_status(executor, body.pki_dir)
    return {
        "easyrsa_path": body.easyrsa_path,
        "pki_dir": body.pki_dir,
        "use_sudo": body.use_sudo,
        "pki_initialized": status["pki_initialized"],
        "ca_built": status["ca_built"],
        "permission_error": status.get("permission_error", False),
        "error_detail": status.get("error_detail"),
    }


@router.post("/server/{server_id}/init-pki")
async def server_init_pki(
    server_id: int,
    body: ServerInitPki,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    output = await easyrsa_service.init_pki(
        executor, body.easyrsa_path, body.pki_dir, body.force, use_sudo=body.use_sudo,
    )
    return {"message": "PKI initialised", "output": output}


@router.post("/server/{server_id}/build-ca")
async def server_build_ca(
    server_id: int,
    body: ServerBuildCa,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    output = await easyrsa_service.build_ca(
        executor, body.easyrsa_path, body.pki_dir, body.common_name, body.passphrase,
        body.expire_days, use_sudo=body.use_sudo,
    )
    return {"message": "CA built successfully", "output": output}


@router.post("/server/{server_id}/build-server")
async def server_build_server(
    server_id: int,
    body: ServerBuildServerCert,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    output = await easyrsa_service.build_server_full(
        executor, body.easyrsa_path, body.pki_dir, body.common_name,
        body.passphrase or "", body.expire_days, use_sudo=body.use_sudo,
    )
    return {"message": "Server certificate built", "output": output}


@router.post("/server/{server_id}/gen-dh")
async def server_gen_dh(
    server_id: int,
    body: ServerGenDh,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    output = await easyrsa_service.gen_dh(
        executor, body.easyrsa_path, body.pki_dir, use_sudo=body.use_sudo,
    )
    return {"message": "DH parameters generated", "output": output}


@router.post("/server/{server_id}/renew-ca")
async def server_renew_ca(
    server_id: int,
    body: ServerRenewCa,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    await easyrsa_service.renew_ca(executor, body.pki_dir, body.ca_passphrase, body.expire_days)
    return {"message": f"CA certificate renewed for {body.expire_days} days", "pki_dir": body.pki_dir}


@router.post("/server/{server_id}/cross-sign")
async def server_cross_sign(
    server_id: int,
    body: ServerCrossSign,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    server = await get_server(db, server_id)
    executor = get_executor(server)
    cross_cert_pem = await easyrsa_service.cross_sign_ca(
        executor, body.pki_dir, body.new_ca_csr_pem, body.old_ca_passphrase, body.expire_days,
    )
    return {"message": "Cross-signed certificate generated", "cross_cert_pem": cross_cert_pem}
