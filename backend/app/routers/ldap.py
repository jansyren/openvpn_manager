"""LDAP / Active Directory management router."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import decrypt_ldap_password, encrypt_ldap_password, hash_password
from app.db.models.ldap_config import LdapConfig
from app.db.models.ldap_group_mapping import LdapGroupRoleMapping
from app.db.models.user import User
from app.db.models.vpn_client import VpnClient
from app.db.models.vpn_instance import VpnInstance
from app.db.models.vpn_instance_ldap_group import VpnInstanceLdapGroup
from app.db.session import get_db
from app.dependencies import get_current_superuser
from app.schemas.ldap import (
    LdapConfigCreate,
    LdapConfigRead,
    LdapConfigUpdate,
    LdapGroupRoleMappingCreate,
    LdapGroupRoleMappingRead,
    LdapSyncResult,
    LdapTestResult,
    VpnInstanceLdapGroupCreate,
    VpnInstanceLdapGroupRead,
)
from app.services import ldap_auth_plugin, ldap_service
from app.services.auth_service import persist_user_roles
from app.services.server_service import get_executor, get_server

router = APIRouter(prefix="/ldap", tags=["ldap"])


# ── LDAP Config CRUD ─────────────────────────────────────────────────────────

@router.get("/configs", response_model=list[LdapConfigRead])
async def list_configs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> list[LdapConfigRead]:
    result = await db.execute(select(LdapConfig).order_by(LdapConfig.id))
    return [LdapConfigRead.model_validate(c) for c in result.scalars().all()]


@router.post("/configs", response_model=LdapConfigRead, status_code=201)
async def create_config(
    body: LdapConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> LdapConfigRead:
    cfg = LdapConfig(
        name=body.name,
        server_url=body.server_url,
        server_url_backup=body.server_url_backup,
        bind_dn=body.bind_dn,
        bind_password_encrypted=encrypt_ldap_password(body.bind_password),
        user_search_base=body.user_search_base,
        user_filter=body.user_filter,
        username_attr=body.username_attr,
        group_search_base=body.group_search_base,
        group_member_attr=body.group_member_attr,
        use_tls=body.use_tls,
        tls_verify_cert=body.tls_verify_cert,
        ca_cert_pem=body.ca_cert_pem,
        is_active=body.is_active,
    )
    db.add(cfg)
    await db.flush()
    return LdapConfigRead.model_validate(cfg)


@router.get("/configs/{config_id}", response_model=LdapConfigRead)
async def get_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> LdapConfigRead:
    cfg = await _get_config_or_404(db, config_id)
    return LdapConfigRead.model_validate(cfg)


@router.put("/configs/{config_id}", response_model=LdapConfigRead)
async def update_config(
    config_id: int,
    body: LdapConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> LdapConfigRead:
    cfg = await _get_config_or_404(db, config_id)
    data = body.model_dump(exclude_unset=True)
    if "bind_password" in data:
        cfg.bind_password_encrypted = encrypt_ldap_password(data.pop("bind_password"))
    for field, value in data.items():
        setattr(cfg, field, value)
    await db.flush()
    return LdapConfigRead.model_validate(cfg)


@router.delete("/configs/{config_id}", status_code=204)
async def delete_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> None:
    cfg = await _get_config_or_404(db, config_id)
    await db.delete(cfg)
    await db.flush()


@router.post("/configs/{config_id}/test", response_model=LdapTestResult)
async def test_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> LdapTestResult:
    cfg = await _get_config_or_404(db, config_id)
    success, message = await ldap_service.test_connection(cfg)
    return LdapTestResult(success=success, message=message)


# ── Group → Role Mappings ────────────────────────────────────────────────────

@router.get("/configs/{config_id}/group-mappings", response_model=list[LdapGroupRoleMappingRead])
async def list_group_mappings(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> list[LdapGroupRoleMappingRead]:
    await _get_config_or_404(db, config_id)
    result = await db.execute(
        select(LdapGroupRoleMapping).where(LdapGroupRoleMapping.ldap_config_id == config_id)
    )
    return [LdapGroupRoleMappingRead.model_validate(m) for m in result.scalars().all()]


@router.post("/configs/{config_id}/group-mappings", response_model=LdapGroupRoleMappingRead, status_code=201)
async def create_group_mapping(
    config_id: int,
    body: LdapGroupRoleMappingCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> LdapGroupRoleMappingRead:
    await _get_config_or_404(db, config_id)
    mapping = LdapGroupRoleMapping(
        ldap_config_id=config_id,
        group_dn=body.group_dn,
        role=body.role,
    )
    db.add(mapping)
    await db.flush()
    return LdapGroupRoleMappingRead.model_validate(mapping)


@router.delete("/configs/{config_id}/group-mappings/{mapping_id}", status_code=204)
async def delete_group_mapping(
    config_id: int,
    mapping_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> None:
    result = await db.execute(
        select(LdapGroupRoleMapping).where(
            LdapGroupRoleMapping.id == mapping_id,
            LdapGroupRoleMapping.ldap_config_id == config_id,
        )
    )
    mapping = result.scalar_one_or_none()
    if mapping is None:
        raise NotFoundError(f"Group mapping {mapping_id} not found")
    await db.delete(mapping)
    await db.flush()


# ── VPN Instance LDAP Groups ─────────────────────────────────────────────────

@router.get("/vpn-instances/{instance_id}/groups", response_model=list[VpnInstanceLdapGroupRead])
async def list_instance_ldap_groups(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> list[VpnInstanceLdapGroupRead]:
    result = await db.execute(
        select(VpnInstanceLdapGroup).where(VpnInstanceLdapGroup.vpn_instance_id == instance_id)
    )
    return [VpnInstanceLdapGroupRead.model_validate(g) for g in result.scalars().all()]


@router.post("/vpn-instances/{instance_id}/groups", response_model=VpnInstanceLdapGroupRead, status_code=201)
async def add_instance_ldap_group(
    instance_id: int,
    body: VpnInstanceLdapGroupCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> VpnInstanceLdapGroupRead:
    await _get_instance_or_404(db, instance_id)
    await _get_config_or_404(db, body.ldap_config_id)
    grp = VpnInstanceLdapGroup(
        vpn_instance_id=instance_id,
        ldap_config_id=body.ldap_config_id,
        group_dn=body.group_dn,
        display_name=body.display_name,
    )
    db.add(grp)
    await db.flush()
    return VpnInstanceLdapGroupRead.model_validate(grp)


@router.delete("/vpn-instances/{instance_id}/groups/{group_id}", status_code=204)
async def remove_instance_ldap_group(
    instance_id: int,
    group_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> None:
    result = await db.execute(
        select(VpnInstanceLdapGroup).where(
            VpnInstanceLdapGroup.id == group_id,
            VpnInstanceLdapGroup.vpn_instance_id == instance_id,
        )
    )
    grp = result.scalar_one_or_none()
    if grp is None:
        raise NotFoundError(f"LDAP group {group_id} not found on instance {instance_id}")
    await db.delete(grp)
    await db.flush()


# ── Deploy LDAP Auth Plugin ───────────────────────────────────────────────────

@router.post("/vpn-instances/{instance_id}/deploy")
async def deploy_ldap_auth(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_superuser),
) -> dict:
    """Deploy the Python LDAP auth script and per-instance JSON config to the VPN server.

    Returns the script path, config path, and the directives to add to server config.
    """
    instance = await _get_instance_or_404(db, instance_id)
    if not instance.ldap_config_id:
        raise ValidationError("No LDAP config assigned to this VPN instance. Set ldap_config_id first.")

    ldap_cfg = await _get_config_or_404(db, instance.ldap_config_id)
    server = await get_server(db, instance.server_id)
    executor = get_executor(server)

    # Collect VPN group DNs for this instance
    grp_result = await db.execute(
        select(VpnInstanceLdapGroup).where(VpnInstanceLdapGroup.vpn_instance_id == instance_id)
    )
    vpn_group_dns = [g.group_dn for g in grp_result.scalars().all()]

    bind_password = decrypt_ldap_password(ldap_cfg.bind_password_encrypted)

    script_path = await ldap_auth_plugin.deploy_script(executor, server.use_sudo)
    config_path = await ldap_auth_plugin.write_instance_config(
        executor,
        instance_id,
        ldap_cfg,
        bind_password,
        vpn_group_dns,
        instance.enforce_cn_username,
        server.use_sudo,
    )

    return {
        "script_path": script_path,
        "config_path": config_path,
        "config_directives": ldap_auth_plugin.instance_config_directives(instance_id),
    }


# ── Sync LDAP Users to VPN Clients ───────────────────────────────────────────

@router.post("/vpn-instances/{instance_id}/sync", response_model=LdapSyncResult)
async def sync_ldap_users(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_superuser),
) -> LdapSyncResult:
    """Sync members of the configured LDAP groups to VPN clients for this instance.

    For each LDAP group member:
    - Creates a User record (role=vpn_user, auth_source=ldap) if absent
    - Creates a VpnClient record if absent
    - Issues a certificate if the instance PKI is configured and a CA passphrase is available
    """
    from app.core.security import decrypt_ca_passphrase
    from app.services import easyrsa_service

    instance = await _get_instance_or_404(db, instance_id)
    if not instance.ldap_config_id:
        raise ValidationError("No LDAP config assigned to this VPN instance.")

    ldap_cfg = await _get_config_or_404(db, instance.ldap_config_id)

    # Load LDAP groups for this instance
    grp_result = await db.execute(
        select(VpnInstanceLdapGroup).where(VpnInstanceLdapGroup.vpn_instance_id == instance_id)
    )
    ldap_groups = grp_result.scalars().all()
    if not ldap_groups:
        raise ValidationError("No LDAP groups configured for this VPN instance.")

    # PKI / cert issuing setup
    pki_dir = instance.pki_dir or "/etc/easy-rsa/pki"
    easyrsa_server_id = instance.easyrsa_server_id or instance.server_id
    vpn_server = await get_server(db, instance.server_id)
    easyrsa_server = await get_server(db, easyrsa_server_id)
    easyrsa_executor = get_executor(easyrsa_server)

    ca_passphrase: str | None = None
    if instance.ca_passphrase_encrypted_blob:
        ca_passphrase = decrypt_ca_passphrase(instance.ca_passphrase_encrypted_blob)
    has_pki = bool(instance.easyrsa_path and instance.pki_dir)

    # Group role mappings (for all LDAP configs — or just this config)
    mapping_result = await db.execute(
        select(LdapGroupRoleMapping).where(LdapGroupRoleMapping.ldap_config_id == ldap_cfg.id)
    )
    group_mappings = mapping_result.scalars().all()

    users_created = 0
    clients_created = 0
    certs_issued = 0
    skipped = 0
    failed: list[str] = []

    # First pass: gather members across all configured groups for this instance,
    # accumulating every group DN a username was found in (a user may be a member
    # of more than one configured group, and needs the full set to resolve role).
    accumulated: dict[str, dict] = {}
    for ldap_group in ldap_groups:
        try:
            members = await ldap_service.search_group_members(ldap_cfg, ldap_group.group_dn)
        except Exception as exc:
            failed.append(f"Group {ldap_group.group_dn}: {exc}")
            continue

        for member in members:
            entry = accumulated.setdefault(member["username"], {**member, "group_dns": set()})
            entry["group_dns"].add(ldap_group.group_dn)

    # Second pass: resolve role from each member's full accumulated group_dns
    # (only reflects membership among groups configured for this instance; the
    # user's first real login re-fetches their true full memberOf and self-corrects).
    for username, member in accumulated.items():
        try:
            # ── Ensure User record ───────────────────────────────────────
            user_result = await db.execute(select(User).where(User.username == username))
            user = user_result.scalar_one_or_none()
            if user is None:
                all_roles = ldap_service.determine_all_roles(list(member["group_dns"]), list(group_mappings))
                role = ldap_service.pick_primary_role(all_roles) or "vpn_user"
                user = User(
                    username=username,
                    hashed_password="!ldap",
                    auth_source="ldap",
                    ldap_dn=member.get("dn"),
                    ldap_config_id=ldap_cfg.id,
                    role=role,
                    is_active=True,
                    is_superuser=False,
                )
                db.add(user)
                await db.flush()
                await persist_user_roles(db, user, all_roles)
                users_created += 1

            # ── Ensure VpnClient record ──────────────────────────────────
            client_result = await db.execute(
                select(VpnClient).where(
                    VpnClient.vpn_instance_id == instance_id,
                    VpnClient.name == username,
                )
            )
            client = client_result.scalar_one_or_none()
            if client is not None:
                skipped += 1
                continue

            # Issue certificate if PKI is available
            cert_serial: str | None = None
            not_before = not_after = None
            if has_pki and ca_passphrase:
                try:
                    await easyrsa_service.build_client_full(
                        easyrsa_executor,
                        instance.easyrsa_path,
                        pki_dir,
                        username,
                        ca_passphrase,
                        use_sudo=instance.easyrsa_use_sudo,
                        expire_days=825,
                    )
                    cert_pem = await easyrsa_service.read_cert(
                        easyrsa_executor, pki_dir, username, use_sudo=instance.easyrsa_use_sudo
                    )
                    info = easyrsa_service.parse_cert_info(cert_pem)
                    cert_serial = info.get("serial")
                    not_before = info.get("not_before")
                    not_after = info.get("not_after")
                    if cert_serial:
                        from app.db.models.certificate import Certificate
                        cert_record = Certificate(
                            vpn_instance_id=instance_id,
                            common_name=username,
                            serial=cert_serial,
                            cert_type="client",
                            not_before=not_before,
                            not_after=not_after,
                            is_revoked=False,
                        )
                        db.add(cert_record)
                    certs_issued += 1
                except Exception as cert_exc:
                    failed.append(f"{username} cert: {cert_exc}")

            client = VpnClient(
                vpn_instance_id=instance_id,
                name=username,
                client_type="user",
                email=member.get("email"),
                cert_serial=cert_serial,
                is_revoked=False,
                created_by=_current_user.id,
            )
            db.add(client)
            await db.flush()
            clients_created += 1

        except Exception as exc:
            failed.append(f"{username}: {exc}")

    return LdapSyncResult(
        users_created=users_created,
        clients_created=clients_created,
        certs_issued=certs_issued,
        skipped=skipped,
        failed=failed,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_config_or_404(db: AsyncSession, config_id: int) -> LdapConfig:
    result = await db.execute(select(LdapConfig).where(LdapConfig.id == config_id))
    cfg = result.scalar_one_or_none()
    if cfg is None:
        raise NotFoundError(f"LDAP config {config_id} not found")
    return cfg


async def _get_instance_or_404(db: AsyncSession, instance_id: int) -> VpnInstance:
    result = await db.execute(select(VpnInstance).where(VpnInstance.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        raise NotFoundError(f"VPN instance {instance_id} not found")
    return instance
