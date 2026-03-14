"""
PAM / system user management service.

SECURITY: Passwords are NEVER passed on the command line.
They are written to the subprocess stdin pipe only.
"""
import re

from app.core.exceptions import ValidationError
from app.services.remote.base import Executor

_USERADD = "/usr/sbin/useradd"
_USERMOD = "/usr/sbin/usermod"
_USERDEL = "/usr/sbin/userdel"
_PASSWD = "/usr/bin/passwd"
_GETENT = "/usr/bin/getent"
_SUDO = "/usr/bin/sudo"


def _maybe_sudo(cmd: list[str], use_sudo: bool) -> list[str]:
    return [_SUDO, "-n"] + cmd if use_sudo else cmd

_UNIX_USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_\-]{0,30}$")
_GROUP_RE = _UNIX_USERNAME_RE


def _validate_username(username: str) -> None:
    if not _UNIX_USERNAME_RE.match(username):
        raise ValidationError(f"Invalid UNIX username: {username!r}")


def _validate_group(group: str) -> None:
    if not _GROUP_RE.match(group):
        raise ValidationError(f"Invalid group name: {group!r}")


async def create_user(
    executor: Executor,
    username: str,
    password: str,
    groups: list[str] | None = None,
    use_sudo: bool = False,
) -> None:
    _validate_username(username)
    if groups:
        for g in groups:
            _validate_group(g)

    # -M: no home directory, -s nologin: no interactive login shell
    cmd = [_USERADD, "-M", "-s", "/usr/sbin/nologin"]
    if groups:
        cmd += ["--groups", ",".join(groups)]
    cmd.append(username)

    result = await executor.run_command(_maybe_sudo(cmd, use_sudo), timeout=15.0)
    result.raise_on_error(f"useradd {username}")

    await _set_password(executor, username, password, use_sudo=use_sudo)


async def update_user(
    executor: Executor,
    username: str,
    password: str | None = None,
    groups: list[str] | None = None,
    use_sudo: bool = False,
) -> None:
    _validate_username(username)

    if groups is not None:
        for g in groups:
            _validate_group(g)
        result = await executor.run_command(
            _maybe_sudo([_USERMOD, "-G", ",".join(groups), username], use_sudo),
            timeout=15.0,
        )
        result.raise_on_error(f"usermod {username}")

    if password is not None:
        await _set_password(executor, username, password, use_sudo=use_sudo)


async def delete_user(executor: Executor, username: str, remove_home: bool = False, use_sudo: bool = False) -> None:
    _validate_username(username)
    cmd = [_USERDEL]
    if remove_home:
        cmd.append("--remove")
    cmd.append(username)
    result = await executor.run_command(_maybe_sudo(cmd, use_sudo), timeout=15.0)
    result.raise_on_error(f"userdel {username}")


async def list_users_in_group(executor: Executor, group: str) -> list[dict]:
    _validate_group(group)
    result = await executor.run_command([_GETENT, "group", group], timeout=10.0)
    if not result.success:
        return []

    # Format: groupname:password:gid:members
    parts = result.stdout.strip().split(":")
    members = parts[3].split(",") if len(parts) > 3 and parts[3] else []
    return [{"username": m.strip()} for m in members if m.strip()]


async def list_groups(executor: Executor) -> list[dict]:
    result = await executor.run_command([_GETENT, "group"], timeout=10.0)
    result.raise_on_error("getent group")

    groups = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(":")
        if len(parts) >= 3:
            name = parts[0]
            gid = int(parts[2]) if parts[2].isdigit() else None
            members = parts[3].split(",") if len(parts) > 3 and parts[3] else []
            groups.append({"name": name, "gid": gid, "members": [m for m in members if m]})
    return groups


async def _set_password(executor: Executor, username: str, password: str, use_sudo: bool = False) -> None:
    """Set password via stdin — never via command-line argument."""
    _validate_username(username)
    # chpasswd reads "username:password" from stdin
    stdin_data = f"{username}:{password}\n".encode()
    result = await executor.run_command(
        _maybe_sudo(["/usr/sbin/chpasswd"], use_sudo),
        timeout=10.0,
        stdin_data=stdin_data,
    )
    if not result.success:
        # Fallback: passwd --stdin (RHEL/CentOS style)
        stdin_data2 = f"{password}\n{password}\n".encode()
        result2 = await executor.run_command(
            _maybe_sudo([_PASSWD, "--stdin", username], use_sudo),
            timeout=10.0,
            stdin_data=stdin_data2,
        )
        result2.raise_on_error(f"setting password for {username}")
