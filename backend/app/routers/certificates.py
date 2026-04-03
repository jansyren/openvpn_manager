from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.certificate import Certificate
from app.db.models.user import User
from app.db.models.vpn_client import VpnClient
from app.db.models.vpn_instance import VpnInstance
from app.db.session import get_db
from app.dependencies import get_current_superuser, get_current_user
from app.schemas.certificate import CertificateRead, CertificateRenew, CertificateRevoke
from app.services import easyrsa_service
from app.services.server_service import get_executor, get_server

router = APIRouter(prefix="/certificates", tags=["certificates"])

_DEFAULT_PKI_DIR = "/etc/easy-rsa/pki"


def _resolve_pki_dir(instance: VpnInstance) -> str:
    return instance.pki_dir or _DEFAULT_PKI_DIR


async def _get_instance_for_cert(cert: Certificate, db: AsyncSession) -> VpnInstance | None:
    result = await db.execute(
        select(VpnInstance).where(VpnInstance.id == cert.vpn_instance_id)
    )
    return result.scalar_one_or_none()


@router.get("", response_model=list[CertificateRead])
async def list_certificates(
    vpn_instance_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[CertificateRead]:
    query = select(Certificate)
    if vpn_instance_id is not None:
        query = query.where(Certificate.vpn_instance_id == vpn_instance_id)
    result = await db.execute(query.order_by(Certificate.common_name))
    return [CertificateRead.model_validate(c) for c in result.scalars().all()]


@router.get("/{cert_id}", response_model=CertificateRead)
async def get_certificate(
    cert_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CertificateRead:
    result = await db.execute(select(Certificate).where(Certificate.id == cert_id))
    cert = result.scalar_one_or_none()
    if cert is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Certificate {cert_id} not found")
    return CertificateRead.model_validate(cert)


@router.post("/{cert_id}/revoke")
async def revoke_certificate(
    cert_id: int,
    body: CertificateRevoke,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    from app.core.exceptions import NotFoundError

    result = await db.execute(select(Certificate).where(Certificate.id == cert_id))
    cert = result.scalar_one_or_none()
    if cert is None:
        raise NotFoundError(f"Certificate {cert_id} not found")

    instance = await _get_instance_for_cert(cert, db)

    # Resolve CA passphrase: use provided value or fall back to stored instance passphrase
    ca_passphrase = body.ca_passphrase
    if not ca_passphrase and instance and instance.ca_passphrase_encrypted_blob:
        from app.core.security import decrypt_ca_passphrase
        ca_passphrase = decrypt_ca_passphrase(instance.ca_passphrase_encrypted_blob)

    if ca_passphrase and instance:
        pki_dir = _resolve_pki_dir(instance)
        easyrsa_path = instance.easyrsa_path or easyrsa_service.DEFAULT_EASYRSA_PATH
        easyrsa_server_id = (
            instance.easyrsa_server_id
            if instance.easyrsa_server_id is not None
            else instance.server_id
        )
        server = await get_server(db, easyrsa_server_id)
        executor = get_executor(server)
        await easyrsa_service.revoke_cert(
            executor, easyrsa_path, pki_dir, cert.common_name, ca_passphrase, body.reason,
            use_sudo=instance.easyrsa_use_sudo if instance else False,
        )

        client_result = await db.execute(
            select(VpnClient).where(
                VpnClient.vpn_instance_id == cert.vpn_instance_id,
                VpnClient.cert_serial == cert.serial,
            )
        )
        vpn_client = client_result.scalar_one_or_none()
        if vpn_client:
            vpn_client.is_revoked = True

    cert.is_revoked = True
    cert.revoked_at = datetime.now(UTC)
    cert.revoke_reason = body.reason
    await db.flush()
    return {"message": f"Certificate {cert.common_name} revoked"}


@router.post("/{cert_id}/renew")
async def renew_certificate(
    cert_id: int,
    body: CertificateRenew,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Renew a certificate (same CN, new serial). Requires easy-rsa 3.1+."""
    from app.core.exceptions import NotFoundError

    result = await db.execute(select(Certificate).where(Certificate.id == cert_id))
    cert = result.scalar_one_or_none()
    if cert is None:
        raise NotFoundError(f"Certificate {cert_id} not found")

    instance = await _get_instance_for_cert(cert, db)
    if instance is None:
        raise NotFoundError("VPN instance not found")

    pki_dir = _resolve_pki_dir(instance)
    easyrsa_path = instance.easyrsa_path or easyrsa_service.DEFAULT_EASYRSA_PATH
    easyrsa_server_id = (
        instance.easyrsa_server_id
        if instance.easyrsa_server_id is not None
        else instance.server_id
    )
    server = await get_server(db, easyrsa_server_id)
    executor = get_executor(server)

    # Resolve CA passphrase: use provided value or fall back to stored instance passphrase
    ca_passphrase = body.ca_passphrase
    if not ca_passphrase and instance.ca_passphrase_encrypted_blob:
        from app.core.security import decrypt_ca_passphrase
        ca_passphrase = decrypt_ca_passphrase(instance.ca_passphrase_encrypted_blob)

    await easyrsa_service.renew_cert(
        executor, easyrsa_path, pki_dir, cert.common_name, ca_passphrase or "", body.expire_days,
        use_sudo=instance.easyrsa_use_sudo,
    )

    try:
        cert_pem = await easyrsa_service.read_cert(executor, pki_dir, cert.common_name, use_sudo=instance.easyrsa_use_sudo)
        info = easyrsa_service.parse_cert_info(cert_pem)
        cert.serial = info.get("serial") or cert.serial
        cert.not_before = info.get("not_before") or cert.not_before
        cert.not_after = info.get("not_after") or cert.not_after
        cert.is_revoked = False
        cert.revoked_at = None
        cert.revoke_reason = None
    except Exception:
        pass

    client_result = await db.execute(
        select(VpnClient).where(
            VpnClient.vpn_instance_id == cert.vpn_instance_id,
            VpnClient.name == cert.common_name,
        )
    )
    vpn_client = client_result.scalar_one_or_none()
    if vpn_client:
        vpn_client.cert_serial = cert.serial
        vpn_client.is_revoked = False

    await db.flush()
    return {"message": f"Certificate {cert.common_name} renewed", "serial": cert.serial}


@router.get("/crl/{vpn_instance_id}")
async def download_crl(
    vpn_instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    from app.core.exceptions import NotFoundError

    inst_result = await db.execute(
        select(VpnInstance).where(VpnInstance.id == vpn_instance_id)
    )
    instance = inst_result.scalar_one_or_none()
    if instance is None:
        raise NotFoundError(f"VPN instance {vpn_instance_id} not found")

    pki_dir = _resolve_pki_dir(instance)
    easyrsa_server_id = (
        instance.easyrsa_server_id
        if instance.easyrsa_server_id is not None
        else instance.server_id
    )
    server = await get_server(db, easyrsa_server_id)
    executor = get_executor(server)

    crl_bytes = await easyrsa_service.read_crl(executor, pki_dir)
    return Response(
        content=crl_bytes,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": "attachment; filename=crl.pem"},
    )
