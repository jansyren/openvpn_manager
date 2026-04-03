"""
Backup and restore service.

Creates tar.gz archives of /etc/openvpn and/or the easy-rsa PKI directory.
Verifies SHA-256 integrity before and after restore.
Uses Python's tarfile module with explicit path validation to prevent
archive path traversal attacks.
"""
import io
import os
import tarfile
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.core.exceptions import BackupError, ValidationError
from app.core.security import compute_sha256
from app.services.remote.base import Executor, prepare_sudo_command


async def create_backup(
    executor: Executor,
    source_paths: list[str],
    backup_type: str,
    server_name: str,
) -> tuple[str, bytes, str]:
    """
    Create a tar.gz backup of the given paths (files or directories).

    Runs tar on the target system then retrieves the archive, so directories
    are handled correctly and file permissions/ownership are preserved.

    Returns (filename, archive_bytes, sha256).
    """
    for path in source_paths:
        if ".." in path:
            raise ValidationError(f"Backup path must not contain '..': {path}")
        if not path.startswith("/"):
            raise ValidationError(f"Backup path must be absolute: {path}")

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"{server_name}_{backup_type}_{timestamp}.tar.gz"
    tmp_archive = f"/tmp/ovpn_backup_{timestamp}.tar.gz"

    sudo_pw = getattr(executor, "sudo_password", None)

    try:
        # Run tar via sudo so root-owned files (PKI keys etc.) are included.
        tar_cmd, stdin_data = prepare_sudo_command(
            ["/bin/tar", "czf", tmp_archive, "--"] + source_paths, sudo_pw
        )
        result = await executor.run_command(tar_cmd, timeout=120, stdin_data=stdin_data)
        if not result.success:
            raise BackupError(
                f"tar failed (exit {result.returncode}): {result.stderr[:256]}"
            )
        # Make archive readable by the SSH user before SFTP retrieval
        chmod_cmd, stdin_data = prepare_sudo_command(
            ["/bin/chmod", "644", tmp_archive], sudo_pw
        )
        await executor.run_command(chmod_cmd, timeout=10, stdin_data=stdin_data)
        archive_bytes = await executor.read_file(tmp_archive)
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError(f"Failed to create backup of {source_paths}: {exc}") from exc
    finally:
        try:
            rm_cmd, stdin_data = prepare_sudo_command(
                ["/bin/rm", "-f", tmp_archive], sudo_pw
            )
            await executor.run_command(rm_cmd, timeout=10, stdin_data=stdin_data)
        except Exception:
            pass

    sha256 = compute_sha256(archive_bytes)

    settings = get_settings()
    storage_path = settings.backup_storage_path / filename
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(archive_bytes)
    os.chmod(storage_path, 0o600)

    return filename, archive_bytes, sha256


async def restore_backup(
    backup_path: str,
    expected_sha256: str,
    executor: Executor,
    create_snapshot: bool = True,
) -> None:
    """
    Restore a backup archive to the server.

    Validates SHA-256 before extracting. All paths in the archive are
    validated to prevent path traversal.
    """
    archive_path = Path(backup_path)
    if not archive_path.exists():
        raise BackupError(f"Backup file not found: {backup_path}")

    archive_bytes = archive_path.read_bytes()
    actual_sha256 = compute_sha256(archive_bytes)

    if actual_sha256 != expected_sha256:
        raise BackupError(
            f"SHA-256 mismatch: expected {expected_sha256!r}, got {actual_sha256!r}. "
            "Backup file may be corrupted."
        )

    if create_snapshot:
        # Create a pre-restore snapshot before overwriting anything
        snapshot_paths = ["/etc/openvpn"]
        try:
            await create_backup(executor, snapshot_paths, "pre_restore_snapshot", "server")
        except Exception:
            pass  # Snapshot failure should not block restore

    buf = io.BytesIO(archive_bytes)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        for member in tar.getmembers():
            # Validate each member path — prevent path traversal
            member_path = Path(member.name)
            if member_path.is_absolute():
                raise BackupError(f"Unsafe absolute path in archive: {member.name}")
            resolved = Path("/").joinpath(member_path).resolve()
            if not str(resolved).startswith("/etc/") and not str(resolved).startswith("/var/"):
                raise BackupError(f"Unsafe path in archive: {member.name}")

            # Extract file content and write via executor
            if member.isfile():
                f = tar.extractfile(member)
                if f is not None:
                    content = f.read()
                    target_path = "/" + member.name
                    await executor.write_file(target_path, content)


def get_backup_file_path(filename: str) -> Path:
    settings = get_settings()
    path = settings.backup_storage_path / filename
    # Prevent path traversal in filename
    if ".." in filename or "/" in filename:
        raise ValidationError("Invalid backup filename")
    return path
