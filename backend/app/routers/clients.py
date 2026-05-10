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
from app.dependencies import get_current_operator, get_current_superuser, get_current_user
from app.schemas.vpn_client import VpnClientCreate, VpnClientRead, VpnClientRevoke, VpnClientUpdate
from app.services import easyrsa_service, pam_service
from app.services.client_generator import generate_site_ovpn, generate_user_ovpn
from app.services.server_service import get_executor, get_server

router = APIRouter(prefix="/clients", tags=["clients"])

_DEFAULT_PKI_DIR = "/etc/easy-rsa/pki"


def _resolve_pki_dir(instance: VpnInstance) -> str:
    return instance.pki_dir or _DEFAULT_PKI_DIR


@router.get("", response_model=list[VpnClientRead])
async def list_clients(
    vpn_instance_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[VpnClientRead]:
    query = select(VpnClient)
    if vpn_instance_id is not None:
        query = query.where(VpnClient.vpn_instance_id == vpn_instance_id)
    # vpn_user role may only view their own clients
    if current_user.role == "vpn_user":
        query = query.where(VpnClient.name == current_user.username)
    result = await db.execute(query)
    return [VpnClientRead.model_validate(c) for c in result.scalars().all()]


@router.post("", response_model=VpnClientRead, status_code=201)
async def create_client(
    body: VpnClientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_operator),
) -> VpnClientRead:
    from app.core.exceptions import NotFoundError, ValidationError

    inst_result = await db.execute(
        select(VpnInstance).where(VpnInstance.id == body.vpn_instance_id)
    )
    instance = inst_result.scalar_one_or_none()
    if instance is None:
        raise NotFoundError(f"VPN instance {body.vpn_instance_id} not found")

    pki_dir = _resolve_pki_dir(instance)
    cert_serial: str | None = None
    not_before: datetime | None = None
    not_after: datetime | None = None

    # Helper: resolve easyrsa executor once if needed
    async def _get_easyrsa_executor_and_path():
        easyrsa_server_id = (
            instance.easyrsa_server_id
            if instance.easyrsa_server_id is not None
            else instance.server_id
        )
        srv = await get_server(db, easyrsa_server_id)
        return get_executor(srv), instance.easyrsa_path or easyrsa_service.DEFAULT_EASYRSA_PATH

    if body.import_existing:
        # --- Import mode: verify existing PAM user, import existing PKI cert ---
        if body.client_type == "user":
            server = await get_server(db, instance.server_id)
            executor = get_executor(server)
            verify = await executor.run_command(
                ["/usr/bin/getent", "passwd", body.name], timeout=10.0
            )
            if not verify.success:
                raise ValidationError(f"PAM user {body.name!r} does not exist on the server")

        # Try to import the existing certificate from PKI
        try:
            easyrsa_executor, _ = await _get_easyrsa_executor_and_path()
            cert_pem = await easyrsa_service.read_cert(easyrsa_executor, pki_dir, body.name, use_sudo=instance.easyrsa_use_sudo)
            info = easyrsa_service.parse_cert_info(cert_pem)
            cert_serial = info.get("serial")
            not_before = info.get("not_before")
            not_after = info.get("not_after")
            if cert_serial:
                cert_record = Certificate(
                    vpn_instance_id=body.vpn_instance_id,
                    common_name=body.name,
                    serial=cert_serial,
                    cert_type="client",
                    not_before=not_before,
                    not_after=not_after,
                )
                db.add(cert_record)
                await db.flush()
        except Exception:
            pass  # No cert found in PKI — client created without one
    else:
        # --- Certificate generation ---
        # Resolve CA passphrase: use provided value or fall back to stored instance passphrase
        ca_passphrase = body.ca_passphrase
        if not ca_passphrase and instance.ca_passphrase_encrypted_blob:
            from app.core.security import decrypt_ca_passphrase
            ca_passphrase = decrypt_ca_passphrase(instance.ca_passphrase_encrypted_blob)

        if ca_passphrase:
            easyrsa_executor, easyrsa_path = await _get_easyrsa_executor_and_path()

            await easyrsa_service.build_client_full(
                easyrsa_executor,
                easyrsa_path,
                pki_dir,
                body.name,
                ca_passphrase,
                body.cert_expire_days,
                use_sudo=instance.easyrsa_use_sudo,
            )

            try:
                cert_pem = await easyrsa_service.read_cert(easyrsa_executor, pki_dir, body.name, use_sudo=instance.easyrsa_use_sudo)
                info = easyrsa_service.parse_cert_info(cert_pem)
                cert_serial = info.get("serial")
                not_before = info.get("not_before")
                not_after = info.get("not_after")
            except Exception:
                pass

            cert_record = Certificate(
                vpn_instance_id=body.vpn_instance_id,
                common_name=body.name,
                serial=cert_serial or "",
                cert_type="client",
                not_before=not_before,
                not_after=not_after,
            )
            db.add(cert_record)
            await db.flush()

        # --- PAM user creation (only when pam_password is provided) ---
        if body.client_type == "user" and body.pam_password:
            server = await get_server(db, instance.server_id)
            executor = get_executor(server)
            await pam_service.create_user(
                executor, body.name, body.pam_password, body.pam_groups or ["openvpn"],
                use_sudo=server.use_sudo,
            )

    client = VpnClient(
        vpn_instance_id=body.vpn_instance_id,
        name=body.name,
        client_type=body.client_type,
        email=str(body.email) if body.email else None,
        cert_serial=cert_serial,
        created_by=current_user.id,
    )
    db.add(client)
    await db.flush()
    return VpnClientRead.model_validate(client)


@router.get("/{client_id}", response_model=VpnClientRead)
async def get_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> VpnClientRead:
    result = await db.execute(select(VpnClient).where(VpnClient.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Client {client_id} not found")
    return VpnClientRead.model_validate(client)


@router.put("/{client_id}", response_model=VpnClientRead)
async def update_client(
    client_id: int,
    body: VpnClientUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> VpnClientRead:
    result = await db.execute(select(VpnClient).where(VpnClient.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Client {client_id} not found")
    if body.email is not None:
        client.email = str(body.email)
    await db.flush()
    return VpnClientRead.model_validate(client)


@router.delete("/{client_id}", status_code=204)
async def delete_client(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> None:
    result = await db.execute(select(VpnClient).where(VpnClient.id == client_id))
    client = result.scalar_one_or_none()
    if client:
        await db.delete(client)
        await db.flush()


@router.get("/{client_id}/ovpn")
async def download_ovpn(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    from app.core.exceptions import ForbiddenError, NotFoundError

    result = await db.execute(select(VpnClient).where(VpnClient.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise NotFoundError(f"Client {client_id} not found")
    if current_user.role == "vpn_user" and client.name != current_user.username:
        raise ForbiddenError("Access denied")
    if client.is_revoked:
        raise ForbiddenError("Cannot download config for a revoked client")

    inst_result = await db.execute(
        select(VpnInstance).where(VpnInstance.id == client.vpn_instance_id)
    )
    instance = inst_result.scalar_one_or_none()
    if instance is None:
        raise NotFoundError("VPN instance not found")

    pki_dir = _resolve_pki_dir(instance)
    easyrsa_server_id = (
        instance.easyrsa_server_id
        if instance.easyrsa_server_id is not None
        else instance.server_id
    )
    easyrsa_server = await get_server(db, easyrsa_server_id)
    executor = get_executor(easyrsa_server)
    vpn_server = await get_server(db, instance.server_id)

    use_sudo = instance.easyrsa_use_sudo
    if client.client_type == "user":
        ca_cert = (await easyrsa_service.read_ca_cert(executor, pki_dir, use_sudo=use_sudo)).decode()
        client_cert = (await easyrsa_service.read_cert(executor, pki_dir, client.name, use_sudo=use_sudo)).decode()
        client_key = (await easyrsa_service.read_key(executor, pki_dir, client.name, use_sudo=use_sudo)).decode()

        ovpn = generate_user_ovpn(
            server_host=vpn_server.host or "localhost",
            server_port=instance.port,
            proto=instance.proto,
            ca_cert_pem=ca_cert,
            client_cert_pem=client_cert,
            client_key_pem=client_key,
            auth_user_pass=instance.pam_enabled,
            tls_auth_key=instance.tls_auth_key or None,
        )
    else:
        ovpn = generate_site_ovpn(
            server_host=vpn_server.host or "localhost",
            server_port=instance.port,
            proto=instance.proto,
            ca_cert_path=f"{pki_dir}/ca.crt",
            client_cert_path=f"{pki_dir}/issued/{client.name}.crt",
            client_key_path=f"{pki_dir}/private/{client.name}.key",
        )

    filename = f"{client.name}.ovpn"
    return Response(
        content=ovpn.encode(),
        media_type="application/x-openvpn-profile",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{client_id}/revoke")
async def revoke_client(
    client_id: int,
    body: VpnClientRevoke = VpnClientRevoke(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_operator),
) -> dict:
    from app.core.exceptions import NotFoundError

    result = await db.execute(select(VpnClient).where(VpnClient.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise NotFoundError(f"Client {client_id} not found")

    client.is_revoked = True

    inst_result = await db.execute(
        select(VpnInstance).where(VpnInstance.id == client.vpn_instance_id)
    )
    instance = inst_result.scalar_one_or_none()

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
        easyrsa_server = await get_server(db, easyrsa_server_id)
        executor = get_executor(easyrsa_server)
        await easyrsa_service.revoke_cert(
            executor, easyrsa_path, pki_dir, client.name, ca_passphrase,
            use_sudo=instance.easyrsa_use_sudo,
        )

        if client.cert_serial:
            cert_result = await db.execute(
                select(Certificate).where(
                    Certificate.vpn_instance_id == client.vpn_instance_id,
                    Certificate.serial == client.cert_serial,
                )
            )
            cert = cert_result.scalar_one_or_none()
            if cert:
                cert.is_revoked = True
                cert.revoked_at = datetime.now(UTC)
                cert.revoke_reason = "unspecified"

    await db.flush()
    return {"message": f"Client {client.name} revoked"}


@router.get("/{client_id}/verify-pam")
async def verify_pam(
    client_id: int,
    group: str = "openvpn",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Check whether this client's username exists in the specified PAM group on the VPN server."""
    from app.core.exceptions import NotFoundError

    result = await db.execute(select(VpnClient).where(VpnClient.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise NotFoundError(f"Client {client_id} not found")

    inst_result = await db.execute(
        select(VpnInstance).where(VpnInstance.id == client.vpn_instance_id)
    )
    instance = inst_result.scalar_one_or_none()
    if instance is None:
        return {"pam_verified": False, "reason": "VPN instance not found"}

    server = await get_server(db, instance.server_id)
    executor = get_executor(server)
    users = await pam_service.list_users_in_group(executor, group)
    names = {u["username"] for u in users}
    return {"pam_verified": client.name in names, "username": client.name, "group": group}
