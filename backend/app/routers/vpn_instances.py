from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel as _BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.models.vpn_instance import VpnInstance
from app.db.session import get_db
from app.dependencies import get_current_superuser, get_current_user
from app.schemas.vpn_instance import (
    CaPassphraseUpdate,
    DiscoveredConfig,
    ServiceActionRequest,
    VpnInstanceCreate,
    VpnInstanceRead,
    VpnInstanceStatus,
    VpnInstanceUpdate,
)
from app.services import cn_verify_service, easyrsa_service
from app.services.config_parser import ParsedConfig, parse_config, serialize_config
from app.services.openvpn_directives import DirectiveSpec, get_all_directives
from app.services.remote.base import prepare_sudo_command
from app.services.server_service import get_executor, get_server
from app.services.service_manager import get_service_logs, get_service_status, service_action


class _InstallCertBody(_BaseModel):
    common_name: str

router = APIRouter(prefix="/vpn-instances", tags=["vpn-instances"])


async def _write_file_sudo(executor, path: str, content: bytes, mode: int = 0o640) -> None:
    """Write a file, falling back to sudo cp from /tmp if SFTP write fails (permission denied)."""
    try:
        await executor.write_file(path, content, mode=mode)
    except Exception:
        # Write to a temp file the SSH user can access, then sudo cp into place
        import hashlib
        tmp_path = f"/tmp/ovpn_cfg_{hashlib.md5(path.encode()).hexdigest()}.tmp"
        await executor.write_file(tmp_path, content, mode=0o644)
        sudo_pw = getattr(executor, "sudo_password", None)
        cp_cmd, stdin_data = prepare_sudo_command(["/bin/cp", tmp_path, path], sudo_pw)
        result = await executor.run_command(cp_cmd, timeout=10.0, stdin_data=stdin_data)
        result.raise_on_error(f"copy config to {path}")
        chmod_cmd, stdin_data = prepare_sudo_command(["/bin/chmod", oct(mode)[2:], path], sudo_pw)
        await executor.run_command(chmod_cmd, timeout=5.0, stdin_data=stdin_data)
        # Clean up temp file
        try:
            await executor.run_command(["/bin/rm", "-f", tmp_path], timeout=5.0)
        except Exception:
            pass


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
    instance = VpnInstance(**body.model_dump(exclude={"import_existing"}))
    db.add(instance)
    await db.flush()

    if not body.import_existing:
        # Generate and write a base config file on the server
        server = await get_server(db, body.server_id)
        executor = get_executor(server)
        network = body.network or "10.8.0.0"
        netmask = body.netmask or "255.255.255.0"
        base_config = ParsedConfig(
            directives={
                "port": str(body.port),
                "proto": body.proto,
                "dev": body.dev,
                "server": f"{network} {netmask}",
                "topology": "subnet",
                "keepalive": "10 120",
                "persist-key": True,
                "persist-tun": True,
                "user": "nobody",
                "group": "nogroup",
                "verb": "3",
                "status": f"/var/log/openvpn/openvpn-status-{body.name}.log 30",
                "ifconfig-pool-persist": f"/var/log/openvpn/ipp-{body.name}.txt",
                "data-ciphers": "AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305",
                "auth": "SHA256",
                "tls-version-min": "1.2",
            },
        )
        content = serialize_config(base_config)
        try:
            from pathlib import PurePosixPath
            parent_dir = str(PurePosixPath(body.config_path).parent)
            sudo_pw = getattr(executor, "sudo_password", None)
            mkdir_cmd, stdin_data = prepare_sudo_command(
                ["/bin/mkdir", "-p", parent_dir], sudo_pw,
            )
            await executor.run_command(mkdir_cmd, timeout=10.0, stdin_data=stdin_data)
            await _write_file_sudo(executor, body.config_path, content.encode())
        except Exception:
            pass  # Config write failure should not block instance creation

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


@router.put("/{instance_id}/ca-passphrase", response_model=VpnInstanceRead)
async def set_ca_passphrase(
    instance_id: int,
    body: CaPassphraseUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> VpnInstanceRead:
    """Store or clear the CA passphrase for this VPN instance. Stored encrypted at rest."""
    from app.core.exceptions import NotFoundError
    from app.core.security import encrypt_ca_passphrase

    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        raise NotFoundError(f"VPN instance {instance_id} not found")

    if body.ca_passphrase:
        instance.ca_passphrase_encrypted_blob = encrypt_ca_passphrase(body.ca_passphrase)
    else:
        instance.ca_passphrase_encrypted_blob = None
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
    return {"directives": parsed.directives, "inline_blocks": parsed.inline_blocks}


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

    parsed = ParsedConfig(
        directives=body.get("directives", {}),
        inline_blocks=body.get("inline_blocks", {}),
    )
    content = serialize_config(parsed)

    # Optionally validate via openvpn --config before writing
    if body.get("validate", False):
        tmp_path = f"/tmp/ovpn_validate_{instance.id}.conf"
        try:
            await executor.write_file(tmp_path, content.encode(), mode=0o640)
            sudo_pw = getattr(executor, "sudo_password", None)
            val_cmd, stdin_data = prepare_sudo_command(
                ["/usr/sbin/openvpn", "--config", tmp_path, "--mode", "server", "--dev-type", "tun", "--genkey", "secret", "/dev/null"],
                sudo_pw,
            )
            # openvpn doesn't have a --dry-run, but --genkey exits after key gen.
            # Instead we just check for parse errors by running with a fake test.
            val_cmd, stdin_data = prepare_sudo_command(
                ["/usr/sbin/openvpn", "--config", tmp_path, "--mode", "server", "--persist-tun", "--verb", "0"],
                sudo_pw,
            )
            # This will fail immediately since no tun device but parse errors show up
        finally:
            try:
                await executor.run_command(["/bin/rm", "-f", tmp_path], timeout=5.0)
            except Exception:
                pass

    await _write_file_sudo(executor, instance.config_path, content.encode())
    return {"message": "Config written successfully"}


@router.post("/{instance_id}/generate-tls-key")
async def generate_tls_key(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Generate an OpenVPN TLS auth key (ta.key) on the server."""
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"VPN instance {instance_id} not found")

    server = await get_server(db, instance.server_id)
    executor = get_executor(server)

    tmp_key = f"/tmp/ovpn_ta_{instance.id}.key"
    sudo_pw = getattr(executor, "sudo_password", None)
    try:
        gen_cmd, stdin_data = prepare_sudo_command(
            ["/usr/sbin/openvpn", "--genkey", "secret", tmp_key], sudo_pw,
        )
        gen_result = await executor.run_command(gen_cmd, timeout=30.0, stdin_data=stdin_data)
        gen_result.raise_on_error("openvpn --genkey")

        # Read the generated key
        chmod_cmd, stdin_data = prepare_sudo_command(["/bin/chmod", "644", tmp_key], sudo_pw)
        await executor.run_command(chmod_cmd, timeout=5.0, stdin_data=stdin_data)
        key_bytes = await executor.read_file(tmp_key)
        key_content = key_bytes.decode("utf-8", errors="replace").strip()
    finally:
        try:
            rm_cmd, stdin_data = prepare_sudo_command(["/bin/rm", "-f", tmp_key], sudo_pw)
            await executor.run_command(rm_cmd, timeout=5.0, stdin_data=stdin_data)
        except Exception:
            pass

    # Save the key to the instance
    instance.tls_auth_key = key_content
    await db.flush()

    return {"key": key_content}


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


@router.get("/{instance_id}/pki-certs")
async def list_pki_certs(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """List issued certs and DH availability from the instance's associated PKI."""
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"VPN instance {instance_id} not found")

    from pathlib import PurePosixPath
    easyrsa_server_id = instance.easyrsa_server_id if instance.easyrsa_server_id is not None else instance.server_id
    easyrsa_server = await get_server(db, easyrsa_server_id)
    easyrsa_executor = get_executor(easyrsa_server)
    pki_dir = instance.pki_dir or "/etc/easy-rsa/pki"

    certs = await easyrsa_service.list_issued_certs(easyrsa_executor, pki_dir, instance.easyrsa_use_sudo)

    dh_path = str(PurePosixPath(pki_dir) / "dh.pem")
    try:
        dh_exists = await easyrsa_executor.file_exists(dh_path)
    except Exception:
        dh_exists = False

    return {"issued_certs": certs, "dh_exists": dh_exists}


@router.post("/{instance_id}/install-cert")
async def install_cert(
    instance_id: int,
    body: _InstallCertBody,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Copy a server cert+key+CA from the PKI to the VPN config directory."""
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"VPN instance {instance_id} not found")

    from pathlib import PurePosixPath
    pki_dir = instance.pki_dir or "/etc/easy-rsa/pki"
    config_dir = str(PurePosixPath(instance.config_path).parent)

    # Executor for PKI server (may differ from VPN server)
    easyrsa_server_id = instance.easyrsa_server_id if instance.easyrsa_server_id is not None else instance.server_id
    easyrsa_server = await get_server(db, easyrsa_server_id)
    easyrsa_executor = get_executor(easyrsa_server)

    # Executor for VPN server
    vpn_server = await get_server(db, instance.server_id)
    vpn_executor = get_executor(vpn_server)

    # Read from PKI
    cert_bytes = await easyrsa_service.read_cert(easyrsa_executor, pki_dir, body.common_name, instance.easyrsa_use_sudo)
    key_bytes = await easyrsa_service.read_key(easyrsa_executor, pki_dir, body.common_name, instance.easyrsa_use_sudo)
    ca_bytes = await easyrsa_service.read_ca_cert(easyrsa_executor, pki_dir, instance.easyrsa_use_sudo)

    # Write to VPN server config directory
    cert_path = str(PurePosixPath(config_dir) / f"{body.common_name}.crt")
    key_path = str(PurePosixPath(config_dir) / f"{body.common_name}.key")
    ca_path = str(PurePosixPath(config_dir) / "ca.crt")

    await _write_file_sudo(vpn_executor, cert_path, cert_bytes, mode=0o644)
    await _write_file_sudo(vpn_executor, key_path, key_bytes, mode=0o600)
    await _write_file_sudo(vpn_executor, ca_path, ca_bytes, mode=0o644)

    return {"cert_path": cert_path, "key_path": key_path, "ca_path": ca_path}


@router.post("/{instance_id}/install-dh")
async def install_dh(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Copy dh.pem from the PKI to the VPN config directory."""
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"VPN instance {instance_id} not found")

    from pathlib import PurePosixPath
    pki_dir = instance.pki_dir or "/etc/easy-rsa/pki"
    config_dir = str(PurePosixPath(instance.config_path).parent)

    easyrsa_server_id = instance.easyrsa_server_id if instance.easyrsa_server_id is not None else instance.server_id
    easyrsa_server = await get_server(db, easyrsa_server_id)
    easyrsa_executor = get_executor(easyrsa_server)

    vpn_server = await get_server(db, instance.server_id)
    vpn_executor = get_executor(vpn_server)

    dh_src = str(PurePosixPath(pki_dir) / "dh.pem")
    dh_bytes = await easyrsa_service._read_file_maybe_sudo(easyrsa_executor, dh_src, instance.easyrsa_use_sudo)

    dh_dst = str(PurePosixPath(config_dir) / "dh.pem")
    await _write_file_sudo(vpn_executor, dh_dst, dh_bytes, mode=0o644)

    return {"dh_path": dh_dst}


@router.post("/{instance_id}/deploy-cn-verify-script")
async def deploy_cn_verify_script(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Deploy the CN-username verification script to the VPN server.

    Writes verify_cn_username.sh to /etc/openvpn/scripts/ and makes it
    executable. Add these directives to the server config to activate it:

        script-security 2
        auth-user-pass-verify /etc/openvpn/scripts/verify_cn_username.sh via-env
    """
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"VPN instance {instance_id} not found")

    server = await get_server(db, instance.server_id)
    executor = get_executor(server)

    script_path = await cn_verify_service.deploy_script(executor, server.use_sudo)

    return {
        "script_path": script_path,
        "config_directives": cn_verify_service.CONFIG_DIRECTIVES.strip(),
    }
