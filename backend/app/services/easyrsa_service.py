"""
easy-rsa wrapper service.

All easy-rsa commands are executed via the Executor (never shell=True).
CA passphrases and key passwords are passed via stdin, never on the command line.
"""
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath

from app.core.exceptions import RemoteExecutionError, ValidationError
from app.services.remote.base import Executor, prepare_sudo_command

_SAFE_CN_RE = re.compile(r"^[a-zA-Z0-9_\-\.]{1,64}$")
# CA common names may contain spaces (passed via --req-cn, not used as filenames)
_SAFE_CA_CN_RE = re.compile(r"^[a-zA-Z0-9 _\-\.]{1,64}$")

# Default easy-rsa binary location (can be overridden per VPN instance)
DEFAULT_EASYRSA_PATH = "/usr/share/easy-rsa/easyrsa"


def _easyrsa(easyrsa_path: str, pki_dir: str, *args: str) -> list[str]:
    """Build an easy-rsa command with --pki-dir set explicitly.

    Passing --pki-dir as a CLI argument is more reliable than relying on the
    EASYRSA_PKI environment variable, which can be lost when commands are
    run through sudo or non-login SSH shells.
    """
    return [easyrsa_path, f"--pki-dir={pki_dir}", *args]


def _sudo_wrap(
    executor: Executor,
    cmd: list[str],
    use_sudo: bool,
    app_stdin: bytes | None = None,
) -> tuple[list[str], bytes | None]:
    """Wrap cmd with sudo if needed, combining sudo password + app stdin."""
    if not use_sudo:
        return cmd, app_stdin
    sudo_pw = getattr(executor, "sudo_password", None)
    cmd, sudo_stdin = prepare_sudo_command(cmd, sudo_pw, preserve_env=True)
    if sudo_stdin and app_stdin:
        return cmd, sudo_stdin + app_stdin
    return cmd, sudo_stdin or app_stdin


def _validate_cn(cn: str) -> None:
    if not _SAFE_CN_RE.match(cn):
        raise ValidationError(f"Invalid common name: {cn!r}")


def _validate_ca_cn(cn: str) -> None:
    if not _SAFE_CA_CN_RE.match(cn):
        raise ValidationError(f"Invalid CA common name: {cn!r}")


def _validate_path(path: str) -> None:
    if ".." in path:
        raise ValidationError("easy-rsa path must not contain '..'")
    if not path.startswith("/"):
        raise ValidationError("easy-rsa path must be absolute")


async def init_pki(executor: Executor, easyrsa_path: str, pki_dir: str, force: bool = False, use_sudo: bool = False) -> str:
    _validate_path(easyrsa_path)
    _validate_path(pki_dir)

    if force:
        base_cmd = _easyrsa(easyrsa_path, pki_dir, "--batch", "init-pki")
        app_stdin = "yes\n".encode()
    else:
        base_cmd = _easyrsa(easyrsa_path, pki_dir, "--batch", "init-pki")
        app_stdin = None
    cmd, stdin_data = _sudo_wrap(executor, base_cmd, use_sudo, app_stdin)
    result = await executor.run_command(cmd, timeout=30.0, stdin_data=stdin_data)
    result.raise_on_error("easy-rsa init-pki")
    return result.stdout


async def build_ca(
    executor: Executor,
    easyrsa_path: str,
    pki_dir: str,
    common_name: str,
    passphrase: str,
    expire_days: int = 3650,
    use_sudo: bool = False,
) -> str:
    _validate_path(easyrsa_path)
    _validate_path(pki_dir)
    _validate_ca_cn(common_name)

    base_cmd = _easyrsa(easyrsa_path, pki_dir, "--batch", f"--days={expire_days}", f"--req-cn={common_name}", "build-ca")
    app_stdin = f"{passphrase}\n{passphrase}\n".encode()
    cmd, stdin_data = _sudo_wrap(executor, base_cmd, use_sudo, app_stdin)
    result = await executor.run_command(cmd, timeout=120.0, stdin_data=stdin_data)
    result.raise_on_error("easy-rsa build-ca")
    return result.stdout


async def build_server_full(
    executor: Executor,
    easyrsa_path: str,
    pki_dir: str,
    common_name: str,
    ca_passphrase: str,
    expire_days: int = 3650,
    use_sudo: bool = False,
) -> str:
    _validate_path(easyrsa_path)
    _validate_path(pki_dir)
    _validate_cn(common_name)

    base_cmd = _easyrsa(easyrsa_path, pki_dir, "--batch", f"--days={expire_days}", "build-server-full", common_name, "nopass")
    app_stdin = f"{ca_passphrase}\n".encode()
    cmd, stdin_data = _sudo_wrap(executor, base_cmd, use_sudo, app_stdin)
    result = await executor.run_command(cmd, timeout=180.0, stdin_data=stdin_data)
    result.raise_on_error(f"easy-rsa build-server-full {common_name}")
    return result.stdout


async def build_client_full(
    executor: Executor,
    easyrsa_path: str,
    pki_dir: str,
    common_name: str,
    ca_passphrase: str,
    expire_days: int = 3650,
    use_sudo: bool = False,
) -> str:
    _validate_path(easyrsa_path)
    _validate_path(pki_dir)
    _validate_cn(common_name)

    base_cmd = _easyrsa(easyrsa_path, pki_dir, "--batch", f"--days={expire_days}", "build-client-full", common_name, "nopass")
    app_stdin = f"{ca_passphrase}\n".encode()
    cmd, stdin_data = _sudo_wrap(executor, base_cmd, use_sudo, app_stdin)
    result = await executor.run_command(cmd, timeout=120.0, stdin_data=stdin_data)
    result.raise_on_error(f"easy-rsa build-client-full {common_name}")
    return result.stdout


async def revoke_cert(
    executor: Executor,
    easyrsa_path: str,
    pki_dir: str,
    common_name: str,
    ca_passphrase: str,
    reason: str = "unspecified",
    use_sudo: bool = False,
) -> str:
    _validate_path(easyrsa_path)
    _validate_cn(common_name)

    base_cmd = _easyrsa(easyrsa_path, pki_dir, "--batch", f"--reason={reason}", "revoke", common_name)
    app_stdin = f"yes\n{ca_passphrase}\n".encode()
    cmd, stdin_data = _sudo_wrap(executor, base_cmd, use_sudo, app_stdin)
    result = await executor.run_command(cmd, timeout=30.0, stdin_data=stdin_data)
    result.raise_on_error(f"easy-rsa revoke {common_name}")

    await gen_crl(executor, easyrsa_path, pki_dir, ca_passphrase, use_sudo=use_sudo)
    return result.stdout


async def gen_crl(
    executor: Executor,
    easyrsa_path: str,
    pki_dir: str,
    ca_passphrase: str,
    use_sudo: bool = False,
) -> str:
    _validate_path(easyrsa_path)

    base_cmd = _easyrsa(easyrsa_path, pki_dir, "--batch", "gen-crl")
    app_stdin = f"{ca_passphrase}\n".encode()
    cmd, stdin_data = _sudo_wrap(executor, base_cmd, use_sudo, app_stdin)
    result = await executor.run_command(cmd, timeout=30.0, stdin_data=stdin_data)
    result.raise_on_error("easy-rsa gen-crl")
    return result.stdout


async def gen_dh(executor: Executor, easyrsa_path: str, pki_dir: str, use_sudo: bool = False) -> str:
    _validate_path(easyrsa_path)

    cmd, stdin_data = _sudo_wrap(executor, _easyrsa(easyrsa_path, pki_dir, "gen-dh"), use_sudo)
    result = await executor.run_command(cmd, timeout=600.0, stdin_data=stdin_data)
    result.raise_on_error("easy-rsa gen-dh")
    return result.stdout


async def _read_file_maybe_sudo(executor: Executor, path: str, use_sudo: bool) -> bytes:
    """Read a file via SFTP/direct read; fall back to 'sudo cat' on permission error.

    Tries the unprivileged read first so that files with readable permissions
    (e.g. issued/*.crt at 644) don't require /bin/cat in sudoers.
    Only falls back to sudo when the first attempt raises an error.
    """
    try:
        return await executor.read_file(path)
    except Exception:
        if not use_sudo:
            raise
        # Permission denied — retry via sudo cat
        cmd, stdin_data = _sudo_wrap(executor, ["/bin/cat", path], True)
        result = await executor.run_command(cmd, timeout=10.0, stdin_data=stdin_data)
        result.raise_on_error(f"read file {path}")
        return result.stdout.encode()


async def read_cert(executor: Executor, pki_dir: str, common_name: str, use_sudo: bool = False) -> bytes:
    _validate_path(pki_dir)
    _validate_cn(common_name)
    path = str(PurePosixPath(pki_dir) / "issued" / f"{common_name}.crt")
    return await _read_file_maybe_sudo(executor, path, use_sudo)


async def read_key(executor: Executor, pki_dir: str, common_name: str, use_sudo: bool = False) -> bytes:
    _validate_path(pki_dir)
    _validate_cn(common_name)
    path = str(PurePosixPath(pki_dir) / "private" / f"{common_name}.key")
    return await _read_file_maybe_sudo(executor, path, use_sudo)


async def read_ca_cert(executor: Executor, pki_dir: str, use_sudo: bool = False) -> bytes:
    _validate_path(pki_dir)
    path = str(PurePosixPath(pki_dir) / "ca.crt")
    return await _read_file_maybe_sudo(executor, path, use_sudo)


async def list_issued_certs(executor: Executor, pki_dir: str, use_sudo: bool = False) -> list[str]:
    """Return sorted list of CN names (stems) from pki/issued/*.crt files."""
    issued_dir = str(PurePosixPath(pki_dir) / "issued")
    try:
        files = await executor.list_directory(issued_dir)
        return sorted(PurePosixPath(f).stem for f in files if f.endswith(".crt"))
    except Exception:
        if not use_sudo:
            return []
        sudo_pw = getattr(executor, "sudo_password", None)
        cmd, stdin_data = prepare_sudo_command(["/bin/ls", issued_dir], sudo_pw)
        result = await executor.run_command(cmd, timeout=10.0, stdin_data=stdin_data)
        if result.success:
            return sorted(
                line.replace(".crt", "")
                for line in result.stdout.strip().split("\n")
                if line.endswith(".crt")
            )
        return []


async def read_crl(executor: Executor, pki_dir: str) -> bytes:
    _validate_path(pki_dir)
    path = str(PurePosixPath(pki_dir) / "crl.pem")
    return await executor.read_file(path)


async def pki_status(executor: Executor, pki_dir: str) -> dict:
    """Check if PKI is initialised and CA is built.

    Falls back to `sudo ls` when SFTP returns permission denied (common when
    the PKI directory was created by root via sudo).
    """
    from app.core.exceptions import RemoteExecutionError

    async def _exists(path: str) -> bool:
        try:
            return await executor.file_exists(path)
        except RemoteExecutionError:
            # SFTP permission denied (root-owned PKI dir) — retry via sudo ls.
            # Works with both password-based sudo and NOPASSWD sudo.
            sudo_pw = getattr(executor, "sudo_password", None)
            cmd, stdin_data = prepare_sudo_command(["/bin/ls", path], sudo_pw)
            result = await executor.run_command(cmd, timeout=5.0, stdin_data=stdin_data)
            return result.success

    try:
        # init-pki creates the private/ subdirectory; serial is only created by build-ca
        pki_initialized = await _exists(str(PurePosixPath(pki_dir) / "private"))
        ca_built = await _exists(str(PurePosixPath(pki_dir) / "ca.crt"))
        index_exists = await _exists(str(PurePosixPath(pki_dir) / "index.txt"))
    except RemoteExecutionError as exc:
        return {
            "pki_initialized": False,
            "ca_built": False,
            "index_exists": False,
            "permission_error": True,
            "error_detail": str(exc),
        }

    return {
        "pki_initialized": pki_initialized,
        "ca_built": ca_built,
        "index_exists": index_exists,
        "permission_error": False,
        "error_detail": None,
    }


def parse_cert_info(cert_pem: bytes) -> dict:
    """Parse a PEM certificate and return serial, not_before, not_after, common_name.

    Uses the cryptography library (already a transitive dep via asyncssh).
    Falls back to empty dict if parsing fails (e.g. cert not yet available).
    """
    try:
        from cryptography import x509

        cert = x509.load_pem_x509_certificate(cert_pem)
        cn_attrs = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
        cn = cn_attrs[0].value if cn_attrs else ""
        return {
            "serial": format(cert.serial_number, "X"),
            "not_before": cert.not_valid_before_utc,
            "not_after": cert.not_valid_after_utc,
            "common_name": cn,
        }
    except Exception:
        return {}


async def renew_cert(
    executor: Executor,
    easyrsa_path: str,
    pki_dir: str,
    common_name: str,
    ca_passphrase: str,
    expire_days: int = 825,
    use_sudo: bool = False,
) -> str:
    """Renew a client/server cert (same CN, new serial). Requires easy-rsa 3.1+."""
    _validate_path(easyrsa_path)
    _validate_path(pki_dir)
    _validate_cn(common_name)

    base_cmd = _easyrsa(easyrsa_path, pki_dir, "--batch", f"--days={expire_days}", "renew", common_name, "nopass")
    app_stdin = f"{ca_passphrase}\n".encode()
    cmd, stdin_data = _sudo_wrap(executor, base_cmd, use_sudo, app_stdin)
    result = await executor.run_command(cmd, timeout=120.0, stdin_data=stdin_data)
    result.raise_on_error(f"easy-rsa renew {common_name}")
    return result.stdout


async def renew_ca(
    executor: Executor,
    pki_dir: str,
    ca_passphrase: str,
    expire_days: int = 3650,
) -> str:
    """Renew a self-signed CA certificate using OpenSSL (same key, new expiry).

    This extends the CA validity without invalidating existing issued certificates.
    Does NOT work for intermediate CAs signed by an external root.
    """
    _validate_path(pki_dir)

    ca_crt_path = str(PurePosixPath(pki_dir) / "ca.crt")
    ca_key_path = str(PurePosixPath(pki_dir) / "private" / "ca.key")

    cmd = [
        "/usr/bin/openssl", "x509",
        "-in", ca_crt_path,
        "-signkey", ca_key_path,
        "-days", str(expire_days),
        "-passin", "stdin",
        "-out", ca_crt_path,
    ]
    stdin_data = f"{ca_passphrase}\n".encode()
    result = await executor.run_command(cmd, timeout=60.0, stdin_data=stdin_data)
    result.raise_on_error("openssl renew CA")
    return result.stdout


async def cross_sign_ca(
    executor: Executor,
    pki_dir: str,
    new_ca_csr_pem: str,
    old_ca_passphrase: str,
    expire_days: int = 365,
) -> str:
    """Cross-sign a new CA's CSR with the old CA key.

    Returns the cross-signed certificate PEM (written to stdout by OpenSSL).
    The caller provides the new CA's CSR (Certificate Signing Request).
    """
    _validate_path(pki_dir)

    old_ca_crt_path = str(PurePosixPath(pki_dir) / "ca.crt")
    old_ca_key_path = str(PurePosixPath(pki_dir) / "private" / "ca.key")
    tmp_csr = "/tmp/new_ca_cross.csr"
    tmp_serial = "/tmp/new_ca_cross.srl"

    await executor.write_file(tmp_csr, new_ca_csr_pem.encode(), mode=0o600)

    cmd = [
        "/usr/bin/openssl", "x509",
        "-req",
        "-in", tmp_csr,
        "-CA", old_ca_crt_path,
        "-CAkey", old_ca_key_path,
        "-CAserial", tmp_serial,
        "-CAcreateserial",
        "-days", str(expire_days),
        "-passin", "stdin",
    ]
    stdin_data = f"{old_ca_passphrase}\n".encode()
    try:
        result = await executor.run_command(cmd, timeout=60.0, stdin_data=stdin_data)
        result.raise_on_error("openssl cross-sign CA")
        return result.stdout
    finally:
        for tmp in [tmp_csr, tmp_serial]:
            try:
                await executor.run_command(["/bin/rm", "-f", tmp], timeout=5.0)
            except Exception:
                pass
