"""LDAP/Active Directory integration service.

All network operations are synchronous (ldap3 is sync) and run in a thread
pool via asyncio.get_event_loop().run_in_executor so they don't block the
event loop.
"""
import asyncio
from typing import TYPE_CHECKING

from app.core.security import decrypt_ldap_password

if TYPE_CHECKING:
    from app.db.models.ldap_config import LdapConfig
    from app.db.models.ldap_group_mapping import LdapGroupRoleMapping


# Role priority for determining the highest role from multiple group mappings
ROLE_PRIORITY = {"admin": 4, "operator": 3, "viewer": 2, "vpn_user": 1}


def _make_server(config: "LdapConfig"):
    """Build an ldap3 Server object from a config record."""
    from ldap3 import Server, Tls
    import ssl

    tls = None
    if not config.tls_verify_cert:
        tls = Tls(validate=ssl.CERT_NONE)
    elif config.ca_cert_pem:
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
        tmp.write(config.ca_cert_pem.encode())
        tmp.close()
        tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=tmp.name)

    use_ssl = config.server_url.lower().startswith("ldaps://")
    return Server(config.server_url, use_ssl=use_ssl, tls=tls, connect_timeout=10)


def _bind_service_account(config: "LdapConfig"):
    """Return an authenticated service-account Connection."""
    from ldap3 import Connection

    server = _make_server(config)
    bind_pw = decrypt_ldap_password(config.bind_password_encrypted)
    conn = Connection(server, config.bind_dn, bind_pw, auto_bind=True, receive_timeout=15)
    return conn


# ── Synchronous helpers (run in thread pool) ─────────────────────────────────

def _do_test_connection(config: "LdapConfig") -> tuple[bool, str]:
    try:
        conn = _bind_service_account(config)
        return True, f"Connected to {config.server_url} as {config.bind_dn}"
    except Exception as exc:
        return False, str(exc)


def _do_authenticate(
    config: "LdapConfig", username: str, password: str
) -> tuple[str, list[str]]:
    """Return (user_dn, group_dn_list) or raise ValueError."""
    from ldap3 import Connection, SUBTREE

    conn = _bind_service_account(config)
    server = conn.server

    search_filter = f"(&{config.user_filter}({config.username_attr}={username}))"
    conn.search(
        config.user_search_base,
        search_filter,
        SUBTREE,
        attributes=["distinguishedName", "memberOf"],
    )

    if not conn.entries:
        raise ValueError(f"User '{username}' not found in LDAP directory")

    entry = conn.entries[0]
    user_dn: str = entry.entry_dn

    # Collect groups from memberOf attribute (works for AD and OpenLDAP with memberOf overlay)
    raw_groups = entry["memberOf"].values if "memberOf" in entry else []
    group_dns: list[str] = [str(g) for g in raw_groups]

    # Verify password by attempting to bind as the user
    from ldap3 import Connection as Conn2
    user_conn = Conn2(server, user_dn, password, receive_timeout=15)
    if not user_conn.bind():
        raise ValueError(f"Password verification failed for '{username}'")

    return user_dn, group_dns


def _do_search_group_members(config: "LdapConfig", group_dn: str) -> list[dict]:
    """Return list of {dn, username, email, display_name} for group members."""
    from ldap3 import SUBTREE, BASE

    conn = _bind_service_account(config)

    # Fetch group's member attribute
    conn.search(group_dn, "(objectClass=*)", BASE, attributes=[config.group_member_attr])
    if not conn.entries:
        return []

    raw_members = conn.entries[0][config.group_member_attr].values if config.group_member_attr in conn.entries[0] else []
    member_dns = [str(m) for m in raw_members]

    results: list[dict] = []
    for member_dn in member_dns:
        conn.search(
            member_dn,
            "(objectClass=*)",
            BASE,
            attributes=[config.username_attr, "mail", "displayName"],
        )
        if not conn.entries:
            continue
        e = conn.entries[0]
        username_vals = e[config.username_attr].values if config.username_attr in e else []
        if not username_vals:
            continue
        username = str(username_vals[0]).strip()
        if not username:
            continue
        mail_vals = e["mail"].values if "mail" in e else []
        name_vals = e["displayName"].values if "displayName" in e else []
        results.append({
            "dn": member_dn,
            "username": username,
            "email": str(mail_vals[0]).strip() if mail_vals else None,
            "display_name": str(name_vals[0]).strip() if name_vals else None,
        })

    return results


# ── Async public API ─────────────────────────────────────────────────────────

async def test_connection(config: "LdapConfig") -> tuple[bool, str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _do_test_connection, config)


async def authenticate_user(
    config: "LdapConfig", username: str, password: str
) -> tuple[str, list[str]]:
    """Authenticate against LDAP. Returns (user_dn, [group_dn, ...]).

    Raises ValueError on auth failure.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _do_authenticate, config, username, password)


async def search_group_members(config: "LdapConfig", group_dn: str) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _do_search_group_members, config, group_dn)


def _matching_roles(
    group_dns: list[str],
    group_mappings: list["LdapGroupRoleMapping"],
) -> set[str]:
    """Return the distinct set of roles whose mapped group_dn appears in group_dns."""
    group_dns_lower = {dn.lower() for dn in group_dns}
    return {m.role for m in group_mappings if m.group_dn.lower() in group_dns_lower}


def pick_primary_role(roles: set[str] | list[str]) -> str | None:
    """Return the single highest-priority role from an arbitrary set/list of roles."""
    if not roles:
        return None
    return max(roles, key=lambda r: ROLE_PRIORITY.get(r, 0))


def determine_all_roles(
    group_dns: list[str],
    group_mappings: list["LdapGroupRoleMapping"],
) -> set[str]:
    """Return the FULL set of roles matching this user's group memberships."""
    return _matching_roles(group_dns, group_mappings)


def determine_role(
    group_dns: list[str],
    group_mappings: list["LdapGroupRoleMapping"],
) -> str | None:
    """Return the highest-priority role for a user given their group memberships."""
    return pick_primary_role(_matching_roles(group_dns, group_mappings))
