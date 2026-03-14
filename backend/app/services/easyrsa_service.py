"""
easy-rsa wrapper service.

All easy-rsa commands are executed via the Executor (never shell=True).
CA passphrases and key passwords are passed via stdin, never on the command line.
"""
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath

from app.core.exceptions import RemoteExecutionError, ValidationError
from app.services.remote.base import Executor

_SAFE_CN_RE = re.compile(r"^[a-zA-Z0-9_\-\.]{1,64}$")

# Default easy-rsa binary location (can be overridden per VPN instance)
DEFAULT_EASYRSA_PATH = "/usr/share/easy-rsa/easyrsa"

_SUDO = "/usr/bin/sudo"


def _maybe_sudo(cmd: list[str], use_sudo: bool) -> list[str]:
    """Prepend sudo -En if use_sudo is True. -E preserves env vars (EASYRSA_PKI), -n is non-interactive."""
    return [_SUDO, "-En"] + cmd if use_sudo else cmd


def _validate_cn(cn: str) -> None:
    if not _SAFE_CN_RE.match(cn):
        raise ValidationError(f"Invalid common name: {cn!r}")


def _validate_path(path: str) -> None:
    if ".." in path:
        raise ValidationError("easy-rsa path must not contain '..'")
    if not path.startswith("/"):
        raise ValidationError("easy-rsa path must be absolute")


async def init_pki(executor: Executor, easyrsa_path: str, pki_dir: str, force: bool = False, use_sudo: bool = False) -> str:
    _validate_path(easyrsa_path)
    _validate_path(pki_dir)

    cmd = _maybe_sudo([easyrsa_path, "init-pki"], use_sudo)
    if force:
        cmd = _maybe_sudo([easyrsa_path, "--batch", "init-pki"], use_sudo)

    env_input = "yes\n".encode() if force else None
    result = await executor.run_command(cmd, timeout=30.0, stdin_data=env_input, env={"EASYRSA_PKI": pki_dir})
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
    _validate_cn(common_name)

    cmd = _maybe_sudo([easyrsa_path, "--batch", f"--days={expire_days}", "build-ca"], use_sudo)
    stdin_data = f"{common_name}\n{passphrase}\n{passphrase}\n".encode()
    result = await executor.run_command(cmd, timeout=120.0, stdin_data=stdin_data, env={"EASYRSA_PKI": pki_dir})
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

    cmd = _maybe_sudo([easyrsa_path, "--batch", f"--days={expire_days}", "build-server-full", common_name, "nopass"], use_sudo)
    stdin_data = f"{ca_passphrase}\n".encode()
    result = await executor.run_command(cmd, timeout=180.0, stdin_data=stdin_data, env={"EASYRSA_PKI": pki_dir})
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

    cmd = _maybe_sudo([easyrsa_path, "--batch", f"--days={expire_days}", "build-client-full", common_name, "nopass"], use_sudo)
    stdin_data = f"{ca_passphrase}\n".encode()
    result = await executor.run_command(cmd, timeout=120.0, stdin_data=stdin_data, env={"EASYRSA_PKI": pki_dir})
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

    cmd = _maybe_sudo([easyrsa_path, "--batch", f"--reason={reason}", "revoke", common_name], use_sudo)
    stdin_data = f"yes\n{ca_passphrase}\n".encode()
    result = await executor.run_command(cmd, timeout=30.0, stdin_data=stdin_data, env={"EASYRSA_PKI": pki_dir})
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

    cmd = _maybe_sudo([easyrsa_path, "--batch", "gen-crl"], use_sudo)
    stdin_data = f"{ca_passphrase}\n".encode()
    result = await executor.run_command(cmd, timeout=30.0, stdin_data=stdin_data, env={"EASYRSA_PKI": pki_dir})
    result.raise_on_error("easy-rsa gen-crl")
    return result.stdout


async def gen_dh(executor: Executor, easyrsa_path: str, pki_dir: str, use_sudo: bool = False) -> str:
    _validate_path(easyrsa_path)

    cmd = _maybe_sudo([easyrsa_path, "gen-dh"], use_sudo)
    result = await executor.run_command(cmd, timeout=600.0, env={"EASYRSA_PKI": pki_dir})
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
        # Permission denied — retry via sudo cat (requires /bin/cat in sudoers)
        result = await executor.run_command(
            [_SUDO, "-n", "/bin/cat", path], timeout=10.0
        )
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


async def read_crl(executor: Executor, pki_dir: str) -> bytes:
    _validate_path(pki_dir)
    path = str(PurePosixPath(pki_dir) / "crl.pem")
    return await executor.read_file(path)


async def pki_status(executor: Executor, pki_dir: str) -> dict:
    """Check if PKI is initialised and CA is built.

    Returns permission_error=True (with a message) if the executor user cannot
    read the PKI directory, rather than silently returning False for all flags.
    """
    from app.core.exceptions import RemoteExecutionError

    async def _exists(path: str) -> bool:
        return await executor.file_exists(path)

    try:
        pki_initialized = await _exists(str(PurePosixPath(pki_dir) / "serial"))
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

    cmd = _maybe_sudo([easyrsa_path, "--batch", f"--days={expire_days}", "renew", common_name, "nopass"], use_sudo)
    stdin_data = f"{ca_passphrase}\n".encode()
    result = await executor.run_command(cmd, timeout=120.0, stdin_data=stdin_data, env={"EASYRSA_PKI": pki_dir})
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
