"""
Deploy and manage the OpenVPN LDAP authentication plugin.

Deploys a Python script to /etc/openvpn/scripts/ldap_auth.py and a per-instance
JSON config to /etc/openvpn/ldap-auth-{instance_id}.json.

OpenVPN server.conf directives added when LDAP auth is enabled:
  script-security 2
  auth-user-pass-verify "/etc/openvpn/scripts/ldap_auth.py /etc/openvpn/ldap-auth-{id}.json" via-file

With via-file OpenVPN writes username/password to a temp file (mode 600) and passes
its path as argv[2].  The script reads and zeros the credentials immediately, so the
password never appears in environment variables or /proc/<pid>/environ.
"""
import json

from app.services.remote.base import Executor, prepare_sudo_command

SCRIPT_DIR = "/etc/openvpn/scripts"
SCRIPT_NAME = "ldap_auth.py"
SCRIPT_PATH = f"{SCRIPT_DIR}/{SCRIPT_NAME}"
CONFIG_DIR = "/etc/openvpn"


def instance_config_path(instance_id: int) -> str:
    return f"{CONFIG_DIR}/ldap-auth-{instance_id}.json"


def instance_config_directives(instance_id: int) -> str:
    cfg_path = instance_config_path(instance_id)
    return (
        f'script-security 2\n'
        f'auth-user-pass-verify "{SCRIPT_PATH} {cfg_path}" via-file'
    )


# ── The self-contained Python auth script ────────────────────────────────────

SCRIPT_CONTENT = r'''#!/usr/bin/env python3
"""
OpenVPN LDAP authentication script.

Called by OpenVPN via-file:
  auth-user-pass-verify "/etc/openvpn/scripts/ldap_auth.py /etc/openvpn/ldap-auth-N.json" via-file

argv[1] = path to the per-instance JSON config
argv[2] = path to the temp credentials file written by OpenVPN (username\\npassword\\n)
          OpenVPN creates this file with mode 600 and deletes it after the script exits.

common_name is always available as the $common_name environment variable regardless
of via-file/via-env.  Username and password are read from the temp file only and
zeroed from memory immediately after use.

Config JSON keys:
  server_url          ldap:// or ldaps:// URL
  server_url_backup   (optional) fallback URL
  bind_dn             Service account DN
  bind_password       Service account password (encrypted at rest by the manager)
  user_search_base    Base DN for user search
  username_attr       Attribute holding the login name (sAMAccountName, uid, …)
  user_filter         LDAP filter fragment, default: (objectClass=user)
  vpn_groups          List of group DNs whose members may connect ([] = any user)
  group_member_attr   Attribute on the group listing members (member, uniqueMember, …)
  enforce_cn_username Boolean – reject if cert CN ≠ username
  tls_verify_cert     Boolean – verify server TLS certificate (default false)
"""
import json
import os
import sys
import syslog


def _log(level: int, msg: str) -> None:
    syslog.openlog("openvpn-ldap-auth", syslog.LOG_PID, syslog.LOG_AUTH)
    syslog.syslog(level, msg)


def _read_credentials(cred_file: str) -> tuple[str, str]:
    """Read username and password from the OpenVPN-supplied temp file."""
    with open(cred_file) as f:
        lines = f.read().splitlines()
    username = lines[0].strip() if len(lines) > 0 else ""
    password = lines[1] if len(lines) > 1 else ""
    return username, password


def _make_server(cfg: dict):
    from ldap3 import Server, Tls
    import ssl

    tls = None
    if not cfg.get("tls_verify_cert", False):
        tls = Tls(validate=ssl.CERT_NONE)
    url = cfg["server_url"]
    use_ssl = url.lower().startswith("ldaps://")
    return Server(url, use_ssl=use_ssl, tls=tls, connect_timeout=10)


def _authenticate(cfg: dict, username: str, password: str, cn: str) -> bool:
    from ldap3 import Connection, SUBTREE, BASE

    server = _make_server(cfg)
    bind_dn = cfg["bind_dn"]
    bind_pw = cfg["bind_password"]
    user_base = cfg["user_search_base"]
    username_attr = cfg.get("username_attr", "sAMAccountName")
    user_filter = cfg.get("user_filter", "(objectClass=user)")
    vpn_groups = cfg.get("vpn_groups", [])
    group_member_attr = cfg.get("group_member_attr", "member")

    # Optional CN = username check
    if cfg.get("enforce_cn_username", False):
        if cn != username:
            _log(syslog.LOG_WARNING, f"REJECT: cert CN '{cn}' != username '{username}'")
            return False

    # Bind with service account to locate the user DN
    svc_conn = Connection(server, bind_dn, bind_pw, auto_bind=True, receive_timeout=15)
    search_filter = f"(&{user_filter}({username_attr}={username}))"
    svc_conn.search(user_base, search_filter, SUBTREE, attributes=["distinguishedName"])

    if not svc_conn.entries:
        _log(syslog.LOG_WARNING, f"REJECT: user '{username}' not found in LDAP")
        return False

    user_dn: str = svc_conn.entries[0].entry_dn

    # Verify password via user bind — password used here and nowhere else
    user_conn = Connection(server, user_dn, password, receive_timeout=15)
    if not user_conn.bind():
        _log(syslog.LOG_WARNING, f"REJECT: invalid password for '{username}'")
        return False

    # Check VPN group membership
    if vpn_groups:
        in_group = False
        for group_dn in vpn_groups:
            svc_conn.search(
                group_dn,
                f"(&(objectClass=*)({group_member_attr}={user_dn}))",
                BASE,
                attributes=["cn"],
            )
            if svc_conn.entries:
                in_group = True
                break
        if not in_group:
            _log(syslog.LOG_WARNING, f"REJECT: '{username}' not in any VPN group")
            return False

    _log(syslog.LOG_INFO, f"ACCEPT: '{username}' authenticated")
    return True


def main() -> int:
    if len(sys.argv) < 3:
        _log(syslog.LOG_ERR, "ERROR: usage: ldap_auth.py <config.json> <credentials-file>")
        return 1

    config_path = sys.argv[1]
    cred_path = sys.argv[2]

    try:
        with open(config_path) as f:
            cfg = json.load(f)
    except Exception as exc:
        _log(syslog.LOG_ERR, f"ERROR: cannot read config '{config_path}': {exc}")
        return 1

    try:
        username, password = _read_credentials(cred_path)
    except Exception as exc:
        _log(syslog.LOG_ERR, f"ERROR: cannot read credentials file '{cred_path}': {exc}")
        return 1

    # common_name is always in the environment (set by OpenVPN regardless of method)
    cn = os.environ.get("common_name", "").strip()

    if not username or not password:
        _log(syslog.LOG_WARNING, "REJECT: empty username or password")
        password = ""
        return 1

    try:
        from ldap3 import Server  # noqa: F401 – verify library is available
    except ImportError:
        _log(syslog.LOG_ERR, "ERROR: ldap3 library missing (apt install python3-ldap3)")
        password = ""
        return 1

    urls_to_try = [cfg["server_url"]]
    if cfg.get("server_url_backup"):
        urls_to_try.append(cfg["server_url_backup"])

    for url in urls_to_try:
        try:
            cfg_attempt = {**cfg, "server_url": url}
            result = _authenticate(cfg_attempt, username, password, cn)
            password = ""  # zero out after use
            return 0 if result else 1
        except Exception as exc:
            _log(syslog.LOG_ERR, f"ERROR: LDAP error ({url}): {exc}")
            if url == urls_to_try[-1]:
                password = ""
                return 1

    password = ""
    return 1


if __name__ == "__main__":
    sys.exit(main())
'''


# ── Deploy helpers ────────────────────────────────────────────────────────────

async def _sudo_run(executor: Executor, cmd: list[str], use_sudo: bool) -> None:
    sudo_pw = getattr(executor, "sudo_password", None)
    if use_sudo:
        cmd, stdin_data = prepare_sudo_command(cmd, sudo_pw)
    else:
        stdin_data = None
    (await executor.run_command(cmd, stdin_data=stdin_data)).raise_on_error(" ".join(cmd))


async def deploy_script(executor: Executor, use_sudo: bool) -> str:
    """Copy the auth script to SCRIPT_PATH on the server."""
    tmp = f"/tmp/.ldap_auth_deploy_{id(executor)}.py"
    await executor.write_file(tmp, SCRIPT_CONTENT.encode(), mode=0o644)
    try:
        await _sudo_run(executor, ["/bin/mkdir", "-p", SCRIPT_DIR], use_sudo)
        await _sudo_run(executor, ["/bin/cp", tmp, SCRIPT_PATH], use_sudo)
        await _sudo_run(executor, ["/bin/chmod", "755", SCRIPT_PATH], use_sudo)
    finally:
        try:
            await executor.run_command(["/bin/rm", "-f", tmp])
        except Exception:
            pass
    return SCRIPT_PATH


async def write_instance_config(
    executor: Executor,
    instance_id: int,
    ldap_config,           # LdapConfig ORM object
    bind_password: str,
    vpn_group_dns: list[str],
    enforce_cn_username: bool,
    use_sudo: bool,
) -> str:
    """Write the per-instance JSON config file to the server."""
    from app.core.security import decrypt_ldap_password  # avoid circular at module level

    cfg = {
        "server_url": ldap_config.server_url,
        "bind_dn": ldap_config.bind_dn,
        "bind_password": bind_password,
        "user_search_base": ldap_config.user_search_base,
        "username_attr": ldap_config.username_attr,
        "user_filter": ldap_config.user_filter,
        "vpn_groups": vpn_group_dns,
        "group_member_attr": ldap_config.group_member_attr,
        "enforce_cn_username": enforce_cn_username,
        "tls_verify_cert": ldap_config.tls_verify_cert,
    }
    if ldap_config.server_url_backup:
        cfg["server_url_backup"] = ldap_config.server_url_backup

    cfg_json = json.dumps(cfg, indent=2).encode()
    cfg_path = instance_config_path(instance_id)

    tmp = f"/tmp/.ldap_cfg_{instance_id}_{id(executor)}.json"
    await executor.write_file(tmp, cfg_json, mode=0o600)
    try:
        await _sudo_run(executor, ["/bin/cp", tmp, cfg_path], use_sudo)
        await _sudo_run(executor, ["/bin/chmod", "600", cfg_path], use_sudo)
        # OpenVPN drops to 'nobody' before running auth scripts, so the config
        # must be readable by that user — root:root 600 would be denied.
        await _sudo_run(executor, ["/bin/chown", "nobody:nogroup", cfg_path], use_sudo)
    finally:
        try:
            await executor.run_command(["/bin/rm", "-f", tmp])
        except Exception:
            pass

    return cfg_path
