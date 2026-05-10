"""
PAM / system user management service.

SECURITY: Passwords are NEVER passed on the command line.
They are written to the subprocess stdin pipe only.
"""
import re
import secrets
import string

from app.core.exceptions import ValidationError
from app.services.remote.base import Executor, prepare_sudo_command

_USERADD = "/usr/sbin/useradd"
_USERMOD = "/usr/sbin/usermod"
_USERDEL = "/usr/sbin/userdel"
_PASSWD = "/usr/bin/passwd"
_GETENT = "/usr/bin/getent"
_GROUPADD = "/usr/sbin/groupadd"
_GROUPDEL = "/usr/sbin/groupdel"
_CHPASSWD = "/usr/sbin/chpasswd"

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

    sudo_pw = getattr(executor, "sudo_password", None)

    # -M: no home directory, -s nologin: no interactive login shell
    cmd = [_USERADD, "-M", "-s", "/usr/sbin/nologin"]
    if groups:
        cmd += ["--groups", ",".join(groups)]
    cmd.append(username)

    if use_sudo:
        cmd, stdin_data = prepare_sudo_command(cmd, sudo_pw)
    else:
        stdin_data = None
    result = await executor.run_command(cmd, timeout=15.0, stdin_data=stdin_data)
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
    sudo_pw = getattr(executor, "sudo_password", None)

    if groups is not None:
        for g in groups:
            _validate_group(g)
        cmd = [_USERMOD, "-G", ",".join(groups), username]
        if use_sudo:
            cmd, stdin_data = prepare_sudo_command(cmd, sudo_pw)
        else:
            stdin_data = None
        result = await executor.run_command(cmd, timeout=15.0, stdin_data=stdin_data)
        result.raise_on_error(f"usermod {username}")

    if password is not None:
        await _set_password(executor, username, password, use_sudo=use_sudo)


async def delete_user(executor: Executor, username: str, remove_home: bool = False, use_sudo: bool = False) -> None:
    _validate_username(username)
    sudo_pw = getattr(executor, "sudo_password", None)
    cmd = [_USERDEL]
    if remove_home:
        cmd.append("--remove")
    cmd.append(username)
    if use_sudo:
        cmd, stdin_data = prepare_sudo_command(cmd, sudo_pw)
    else:
        stdin_data = None
    result = await executor.run_command(cmd, timeout=15.0, stdin_data=stdin_data)
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


async def create_group(
    executor: Executor,
    name: str,
    gid: int | None = None,
    use_sudo: bool = False,
) -> None:
    _validate_group(name)
    sudo_pw = getattr(executor, "sudo_password", None)
    cmd = [_GROUPADD]
    if gid is not None:
        cmd += ["--gid", str(gid)]
    cmd.append(name)
    if use_sudo:
        cmd, stdin_data = prepare_sudo_command(cmd, sudo_pw)
    else:
        stdin_data = None
    result = await executor.run_command(cmd, timeout=15.0, stdin_data=stdin_data)
    result.raise_on_error(f"groupadd {name}")


async def delete_group(executor: Executor, name: str, use_sudo: bool = False) -> None:
    _validate_group(name)
    sudo_pw = getattr(executor, "sudo_password", None)
    cmd = [_GROUPDEL, name]
    if use_sudo:
        cmd, stdin_data = prepare_sudo_command(cmd, sudo_pw)
    else:
        stdin_data = None
    result = await executor.run_command(cmd, timeout=15.0, stdin_data=stdin_data)
    result.raise_on_error(f"groupdel {name}")


async def get_user_shadow_hash(executor: Executor, username: str, use_sudo: bool = False) -> str | None:
    """Return the shadow password hash for a user, or None if unavailable."""
    _validate_username(username)
    sudo_pw = getattr(executor, "sudo_password", None)
    cmd = [_GETENT, "shadow", username]
    if use_sudo:
        cmd, stdin_data = prepare_sudo_command(cmd, sudo_pw)
    else:
        stdin_data = None
    result = await executor.run_command(cmd, timeout=10.0, stdin_data=stdin_data)
    if not result.success:
        return None
    parts = result.stdout.strip().split(":")
    if len(parts) < 2:
        return None
    pw_hash = parts[1]
    # Locked/disabled accounts have ! or * instead of a real hash
    if not pw_hash or pw_hash in ("!", "*", "!!", "x"):
        return None
    return pw_hash


async def create_user_with_hash(
    executor: Executor,
    username: str,
    passwd_hash: str | None,
    groups: list[str] | None = None,
    use_sudo: bool = False,
) -> None:
    """Create a user using a pre-hashed password (for cross-server copy)."""
    _validate_username(username)
    if groups:
        for g in groups:
            _validate_group(g)

    sudo_pw = getattr(executor, "sudo_password", None)

    cmd = [_USERADD, "-M", "-s", "/usr/sbin/nologin"]
    if groups:
        cmd += ["--groups", ",".join(groups)]
    cmd.append(username)

    if use_sudo:
        cmd, stdin_data = prepare_sudo_command(cmd, sudo_pw)
    else:
        stdin_data = None
    result = await executor.run_command(cmd, timeout=15.0, stdin_data=stdin_data)
    result.raise_on_error(f"useradd {username}")

    if passwd_hash:
        # chpasswd -e accepts pre-hashed passwords directly
        user_stdin = f"{username}:{passwd_hash}\n".encode()
        chpasswd_cmd: list[str] = [_CHPASSWD, "-e"]
        if use_sudo:
            chpasswd_cmd, sudo_stdin = prepare_sudo_command(chpasswd_cmd, sudo_pw)
            stdin_data2 = (sudo_stdin or b"") + user_stdin
        else:
            stdin_data2 = user_stdin
        result2 = await executor.run_command(chpasswd_cmd, timeout=10.0, stdin_data=stdin_data2)
        result2.raise_on_error(f"chpasswd -e {username}")


def generate_secure_password(length: int = 20) -> str:
    """Generate a cryptographically secure password with at least one of each character class."""
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    symbols = "!@#$%^&*()-_=+"
    all_chars = uppercase + lowercase + digits + symbols
    guaranteed = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(symbols),
    ]
    rest = [secrets.choice(all_chars) for _ in range(length - 4)]
    combined = guaranteed + rest
    import random
    random.SystemRandom().shuffle(combined)
    return "".join(combined)


async def reset_password(executor: Executor, username: str, use_sudo: bool = False) -> str:
    """Generate and set a new secure password. Returns the plaintext password (one-time)."""
    new_password = generate_secure_password()
    await _set_password(executor, username, new_password, use_sudo=use_sudo)
    return new_password


async def _set_password(executor: Executor, username: str, password: str, use_sudo: bool = False) -> None:
    """Set password via stdin — never via command-line argument."""
    _validate_username(username)
    sudo_pw = getattr(executor, "sudo_password", None)

    # chpasswd reads "username:password" from stdin
    user_stdin = f"{username}:{password}\n".encode()
    cmd: list[str] = ["/usr/sbin/chpasswd"]
    if use_sudo:
        cmd, sudo_stdin = prepare_sudo_command(cmd, sudo_pw)
        # sudo -S reads its password first, then passes remaining stdin to child
        stdin_data = (sudo_stdin or b"") + user_stdin
    else:
        stdin_data = user_stdin

    result = await executor.run_command(cmd, timeout=10.0, stdin_data=stdin_data)
    if not result.success:
        # Fallback: passwd --stdin (RHEL/CentOS style)
        user_stdin2 = f"{password}\n{password}\n".encode()
        cmd2: list[str] = [_PASSWD, "--stdin", username]
        if use_sudo:
            cmd2, sudo_stdin2 = prepare_sudo_command(cmd2, sudo_pw)
            stdin_data2 = (sudo_stdin2 or b"") + user_stdin2
        else:
            stdin_data2 = user_stdin2
        result2 = await executor.run_command(cmd2, timeout=10.0, stdin_data=stdin_data2)
        result2.raise_on_error(f"setting password for {username}")
