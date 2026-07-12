"""AUDIT-1: mutations write AuditLog rows visible via /system/audit-log."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_user_create_writes_audit_log(client: AsyncClient, superuser, superuser_token: str):
    headers = {"Authorization": f"Bearer {superuser_token}"}

    created = await client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "auditee", "password": "Auditee12345!", "role": "viewer"},
    )
    assert created.status_code == 201

    log = await client.get("/api/v1/system/audit-log", headers=headers)
    assert log.status_code == 200
    entries = log.json()
    actions = {e["action"] for e in entries}
    assert "user.create" in actions

    entry = next(e for e in entries if e["action"] == "user.create")
    assert entry["resource_type"] == "user"
    assert entry["user_id"] == superuser.id
    assert "auditee" in (entry["detail_json"] or "")


@pytest.mark.asyncio
async def test_server_create_and_delete_are_audited(
    client: AsyncClient, superuser, superuser_token: str
):
    headers = {"Authorization": f"Bearer {superuser_token}"}

    created = await client.post(
        "/api/v1/servers", headers=headers, json={"name": "audit-srv", "is_local": True}
    )
    assert created.status_code == 201
    server_id = created.json()["id"]

    deleted = await client.delete(f"/api/v1/servers/{server_id}", headers=headers)
    assert deleted.status_code == 204

    log = await client.get("/api/v1/system/audit-log", headers=headers)
    actions = {e["action"] for e in log.json()}
    assert {"server.create", "server.delete"} <= actions
