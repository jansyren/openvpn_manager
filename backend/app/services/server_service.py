"""Server CRUD and connection management service."""
import base64

import asyncssh
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, RemoteExecutionError
from app.core.security import encrypt_ssh_key, encrypt_sudo_password
from app.db.models.server import Server
from app.schemas.server import ServerCreate, ServerUpdate
from app.services.remote.local_executor import LocalExecutor
from app.services.remote.remote_executor import RemoteExecutor, _create_connection


async def get_servers(db: AsyncSession) -> list[Server]:
    result = await db.execute(select(Server).order_by(Server.name))
    return list(result.scalars().all())


async def get_server(db: AsyncSession, server_id: int) -> Server:
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if server is None:
        raise NotFoundError(f"Server {server_id} not found")
    return server


async def create_server(db: AsyncSession, data: ServerCreate) -> Server:
    # Check name uniqueness
    existing = await db.execute(select(Server).where(Server.name == data.name))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Server name '{data.name}' already exists")

    kwargs: dict = {
        "name": data.name,
        "description": data.description,
        "is_local": data.is_local,
        "host": data.host,
        "port": data.port,
        "ssh_username": data.ssh_username,
    }

    if data.ssh_private_key_pem:
        key_bytes = data.ssh_private_key_pem.encode()
        kwargs["ssh_key_encrypted_blob"] = encrypt_ssh_key(key_bytes)

    if data.sudo_password:
        kwargs["sudo_password_encrypted_blob"] = encrypt_sudo_password(data.sudo_password)

    server = Server(**kwargs)
    db.add(server)
    await db.flush()
    return server


async def update_server(db: AsyncSession, server_id: int, data: ServerUpdate) -> Server:
    server = await get_server(db, server_id)

    if data.name is not None:
        server.name = data.name
    if data.description is not None:
        server.description = data.description
    if data.host is not None:
        server.host = data.host
    if data.port is not None:
        server.port = data.port
    if data.ssh_username is not None:
        server.ssh_username = data.ssh_username
    if data.ssh_private_key_pem is not None:
        server.ssh_key_encrypted_blob = encrypt_ssh_key(data.ssh_private_key_pem.encode())
    if data.sudo_password is not None:
        server.sudo_password_encrypted_blob = encrypt_sudo_password(data.sudo_password)

    await db.flush()
    return server


async def delete_server(db: AsyncSession, server_id: int) -> None:
    server = await get_server(db, server_id)
    await db.delete(server)
    await db.flush()


async def test_connection(db: AsyncSession, server_id: int) -> dict:
    server = await get_server(db, server_id)

    if server.is_local:
        executor = LocalExecutor()
        result = await executor.run_command(["/bin/uname", "-n"], timeout=5.0)
        if result.success:
            # Store fingerprint as "local"
            server.ssh_host_fingerprint = "local"
            await db.flush()
            return {"success": True, "message": f"Local server: {result.stdout.strip()}", "fingerprint": "local"}
        return {"success": False, "message": result.stderr}

    try:
        conn = await _create_connection(server)
        # Get host fingerprint
        host_key = conn.get_server_host_key()
        fingerprint = host_key.get_fingerprint() if host_key else None

        # Persist fingerprint (TOFU)
        if fingerprint and server.ssh_host_fingerprint is None:
            server.ssh_host_fingerprint = fingerprint
            await db.flush()

        hostname_result = await conn.run("hostname", timeout=5)
        conn.close()

        return {
            "success": True,
            "message": f"Connected to {hostname_result.stdout.strip()}",
            "fingerprint": fingerprint,
        }
    except RemoteExecutionError as exc:
        return {"success": False, "message": str(exc), "fingerprint": None}
    except Exception as exc:
        return {"success": False, "message": f"Connection failed: {exc}", "fingerprint": None}


async def discover_configs(db: AsyncSession, server_id: int, config_dir: str = "/etc/openvpn") -> list[dict]:
    server = await get_server(db, server_id)

    if server.is_local:
        executor = LocalExecutor()
    else:
        executor = RemoteExecutor(server)

    entries = await executor.list_directory(config_dir)
    configs = []
    for path in entries:
        if path.endswith(".conf"):
            name = path.rsplit("/", 1)[-1].removesuffix(".conf")
            try:
                content = await executor.read_file(path)
                configs.append({"path": path, "name": name, "size_bytes": len(content)})
            except Exception:
                configs.append({"path": path, "name": name, "size_bytes": 0})

    return configs


def get_executor(server: Server):
    """Return the appropriate executor for a server."""
    if server.is_local:
        return LocalExecutor()
    return RemoteExecutor(server)
