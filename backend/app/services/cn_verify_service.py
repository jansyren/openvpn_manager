"""
Deploy and manage the CN-username verification script for OpenVPN.

When enforce_cn_username is enabled on a VPN instance, OpenVPN calls this
script via `auth-user-pass-verify ... via-env` to ensure the certificate CN
matches the username supplied at login.
"""
from app.services.remote.base import Executor, prepare_sudo_command

SCRIPT_DIR = "/etc/openvpn/scripts"
SCRIPT_NAME = "verify_cn_username.sh"
SCRIPT_PATH = f"{SCRIPT_DIR}/{SCRIPT_NAME}"

SCRIPT_CONTENT = """\
#!/bin/bash
# verify_cn_username.sh — OpenVPN CN/username enforcement
#
# Called by OpenVPN via:
#   auth-user-pass-verify /etc/openvpn/scripts/verify_cn_username.sh via-env
#   script-security 2
#
# Rejects the connection if the client certificate CN does not match the
# username supplied at login, preventing certificate misuse.

CN="${common_name:-}"
UN="${username:-}"

if [ -z "$CN" ] || [ -z "$UN" ]; then
    logger -t openvpn-verify-cn "REJECT: missing CN or username (CN='$CN' UN='$UN')"
    exit 1
fi

if [ "$CN" = "$UN" ]; then
    logger -t openvpn-verify-cn "ACCEPT: CN='$CN' matches username"
    exit 0
else
    logger -t openvpn-verify-cn "REJECT: CN='$CN' does not match username='$UN'"
    exit 1
fi
"""

# Directives to add to the OpenVPN server config when enforcement is enabled.
CONFIG_DIRECTIVES = f"""\
script-security 2
auth-user-pass-verify {SCRIPT_PATH} via-env
"""


async def deploy_script(executor: Executor, use_sudo: bool) -> str:
    """Write the verification script to the server and make it executable.

    Returns the absolute path where the script was installed.
    """
    tmp_path = f"/tmp/.verify_cn_deploy_{id(executor)}.sh"
    sudo_pw = getattr(executor, "sudo_password", None)

    # 1. Write to /tmp (SSH user always has write access there)
    await executor.write_file(tmp_path, SCRIPT_CONTENT.encode(), mode=0o644)

    try:
        # 2. Create destination directory
        mkdir_cmd = ["/bin/mkdir", "-p", SCRIPT_DIR]
        if use_sudo:
            mkdir_cmd, stdin_data = prepare_sudo_command(mkdir_cmd, sudo_pw)
        else:
            stdin_data = None
        (await executor.run_command(mkdir_cmd, stdin_data=stdin_data)).raise_on_error(
            f"mkdir {SCRIPT_DIR}"
        )

        # 3. Copy script to destination
        cp_cmd = ["/bin/cp", tmp_path, SCRIPT_PATH]
        if use_sudo:
            cp_cmd, stdin_data = prepare_sudo_command(cp_cmd, sudo_pw)
        else:
            stdin_data = None
        (await executor.run_command(cp_cmd, stdin_data=stdin_data)).raise_on_error(
            f"cp to {SCRIPT_PATH}"
        )

        # 4. Make executable (root-owned, world-executable, not writable by others)
        chmod_cmd = ["/bin/chmod", "755", SCRIPT_PATH]
        if use_sudo:
            chmod_cmd, stdin_data = prepare_sudo_command(chmod_cmd, sudo_pw)
        else:
            stdin_data = None
        (await executor.run_command(chmod_cmd, stdin_data=stdin_data)).raise_on_error(
            f"chmod {SCRIPT_PATH}"
        )
    finally:
        # 5. Always clean up tmp file
        try:
            await executor.run_command(["/bin/rm", "-f", tmp_path])
        except Exception:
            pass

    return SCRIPT_PATH
