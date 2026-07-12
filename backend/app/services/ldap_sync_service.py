"""Orchestration for syncing LDAP/AD group members into VPN clients.

Kept out of the router so the endpoint stays thin and the two-pass group
accumulation is unit-testable without a live directory.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.core.security import decrypt_ca_passphrase
from app.db.models.certificate import Certificate
from app.db.models.ldap_config import LdapConfig
from app.db.models.ldap_group_mapping import LdapGroupRoleMapping
from app.db.models.user import User
from app.db.models.vpn_client import VpnClient
from app.db.models.vpn_instance import VpnInstance
from app.db.models.vpn_instance_ldap_group import VpnInstanceLdapGroup
from app.db.utils import get_or_404
from app.schemas.ldap import LdapSyncResult
from app.services import easyrsa_service, ldap_service
from app.services.auth_service import persist_user_roles
from app.services.server_service import get_executor, get_server

_DEFAULT_PKI_DIR = "/etc/easy-rsa/pki"


def accumulate_members(group_members: list[tuple[str, list[dict]]]) -> dict[str, dict]:
    """Collapse per-group member lists into one entry per username, accumulating
    the full set of group DNs each username was found in.

    A user may belong to more than one configured group, and needs the union of
    those groups to resolve their role correctly (not just the last one seen).
    """
    accumulated: dict[str, dict] = {}
    for group_dn, members in group_members:
        for member in members:
            entry = accumulated.setdefault(member["username"], {**member, "group_dns": set()})
            entry["group_dns"].add(group_dn)
    return accumulated


async def sync_instance_users(db: AsyncSession, instance_id: int, actor_id: int) -> LdapSyncResult:
    """Sync members of the configured LDAP groups to VPN clients for this instance.

    For each member: create the User (auth_source=ldap) if absent, create the
    VpnClient if absent, and issue a certificate when the instance PKI is
    configured and a CA passphrase is available.
    """
    instance = await get_or_404(db, VpnInstance, instance_id, "VPN instance")
    if not instance.ldap_config_id:
        raise ValidationError("No LDAP config assigned to this VPN instance.")

    ldap_cfg = await get_or_404(db, LdapConfig, instance.ldap_config_id, "LDAP config")

    grp_result = await db.execute(
        select(VpnInstanceLdapGroup).where(VpnInstanceLdapGroup.vpn_instance_id == instance_id)
    )
    ldap_groups = grp_result.scalars().all()
    if not ldap_groups:
        raise ValidationError("No LDAP groups configured for this VPN instance.")

    # PKI / cert issuing setup
    pki_dir = instance.pki_dir or _DEFAULT_PKI_DIR
    easyrsa_server_id = instance.easyrsa_server_id or instance.server_id
    easyrsa_server = await get_server(db, easyrsa_server_id)
    easyrsa_executor = get_executor(easyrsa_server)

    ca_passphrase: str | None = None
    if instance.ca_passphrase_encrypted_blob:
        ca_passphrase = decrypt_ca_passphrase(instance.ca_passphrase_encrypted_blob)
    has_pki = bool(instance.easyrsa_path and instance.pki_dir)

    mapping_result = await db.execute(
        select(LdapGroupRoleMapping).where(LdapGroupRoleMapping.ldap_config_id == ldap_cfg.id)
    )
    group_mappings = list(mapping_result.scalars().all())

    users_created = 0
    clients_created = 0
    certs_issued = 0
    skipped = 0
    failed: list[str] = []

    # Pass 1: fetch members per configured group (recording per-group failures).
    group_members: list[tuple[str, list[dict]]] = []
    for ldap_group in ldap_groups:
        try:
            members = await ldap_service.search_group_members(ldap_cfg, ldap_group.group_dn)
        except Exception as exc:
            failed.append(f"Group {ldap_group.group_dn}: {exc}")
            continue
        group_members.append((ldap_group.group_dn, members))

    accumulated = accumulate_members(group_members)

    # Pass 2: create users/clients/certs from each member's full group membership.
    for username, member in accumulated.items():
        try:
            user_result = await db.execute(select(User).where(User.username == username))
            user = user_result.scalar_one_or_none()
            if user is None:
                all_roles = ldap_service.determine_all_roles(
                    list(member["group_dns"]), group_mappings
                )
                role = ldap_service.pick_primary_role(all_roles) or "vpn_user"
                user = User(
                    username=username,
                    hashed_password="!ldap",  # noqa: S106 — LDAP sentinel, not a password
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

            client_result = await db.execute(
                select(VpnClient).where(
                    VpnClient.vpn_instance_id == instance_id,
                    VpnClient.name == username,
                )
            )
            if client_result.scalar_one_or_none() is not None:
                skipped += 1
                continue

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
                        db.add(
                            Certificate(
                                vpn_instance_id=instance_id,
                                common_name=username,
                                serial=cert_serial,
                                cert_type="client",
                                not_before=not_before,
                                not_after=not_after,
                                is_revoked=False,
                            )
                        )
                    certs_issued += 1
                except Exception as cert_exc:
                    failed.append(f"{username} cert: {cert_exc}")

            db.add(
                VpnClient(
                    vpn_instance_id=instance_id,
                    name=username,
                    client_type="user",
                    email=member.get("email"),
                    cert_serial=cert_serial,
                    is_revoked=False,
                    created_by=actor_id,
                )
            )
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
