from datetime import datetime

from pydantic import BaseModel, Field


class SystemInfo(BaseModel):
    app_version: str
    openvpn_version: str | None
    python_version: str
    environment: str


class HealthCheck(BaseModel):
    status: str = "ok"
    database: str = "ok"


class AuditLogEntry(BaseModel):
    id: int
    user_id: int | None
    action: str
    resource_type: str
    resource_id: str | None
    detail_json: str | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogPurgeRequest(BaseModel):
    older_than_days: int = Field(..., ge=1, le=3650)


class DeployPrerequisites(BaseModel):
    server_id: int
    os_compatible: bool
    os_version: str | None
    openvpn_installed: bool
    easyrsa_installed: bool
    disk_space_gb: float | None
    ready_to_deploy: bool
    notes: list[str]


class DeployRequest(BaseModel):
    openvpn_config_dir: str = "/etc/openvpn"
    easyrsa_install_dir: str = "/etc/easy-rsa"
    install_openvpn: bool = True
    install_easyrsa: bool = True


class DeployTaskStatus(BaseModel):
    task_id: str
    status: str  # pending | running | completed | failed
    log_lines: list[str]
    error: str | None = None
