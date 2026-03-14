from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BackupCreate(BaseModel):
    server_id: int
    backup_type: Literal["full", "easyrsa", "server_config"]
    notes: str | None = Field(None, max_length=512)
    vpn_instance_id: int | None = None


class BackupRead(BaseModel):
    id: int
    server_id: int | None
    filename: str
    size_bytes: int | None
    sha256: str
    backup_type: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RestoreRequest(BaseModel):
    backup_id: int
    # Caller must supply expected SHA-256 to confirm they know what they're restoring
    expected_sha256: str = Field(..., min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    create_pre_restore_snapshot: bool = True
