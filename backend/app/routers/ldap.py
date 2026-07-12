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
from app.db.utils import get_or_404
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
from app.services import ldap_auth_plugin, ldap_service, ldap_sync_service
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

    For each LDAP group member: create the User (auth_source=ldap) if absent,
    create the VpnClient if absent, and issue a certificate when the instance PKI
    is configured and a CA passphrase is available. Orchestration lives in
    `ldap_sync_service.sync_instance_users`.
    """
    return await ldap_sync_service.sync_instance_users(db, instance_id, _current_user.id)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_config_or_404(db: AsyncSession, config_id: int) -> LdapConfig:
    return await get_or_404(db, LdapConfig, config_id, "LDAP config")


async def _get_instance_or_404(db: AsyncSession, instance_id: int) -> VpnInstance:
    return await get_or_404(db, VpnInstance, instance_id, "VPN instance")
