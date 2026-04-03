import re

from pydantic import BaseModel, Field, field_validator, model_validator

_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")
_SAFE_PATH_RE = re.compile(r"^(/[a-zA-Z0-9_\-\.]+)+$")


class ServerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_safe(cls, v: str) -> str:
        if not _SAFE_NAME_RE.match(v):
            raise ValueError("name must only contain letters, digits, underscores, and hyphens")
        return v


class ServerCreate(ServerBase):
    is_local: bool = False
    host: str | None = Field(None, max_length=253)
    port: int = Field(22, ge=1, le=65535)
    ssh_username: str | None = Field(None, max_length=64)
    # Base64-encoded private key PEM; will be encrypted server-side
    ssh_private_key_pem: str | None = None
    # Sudo password for elevated commands; will be encrypted server-side
    sudo_password: str | None = None

    @model_validator(mode="after")
    def remote_requires_connection_info(self) -> "ServerCreate":
        if not self.is_local:
            if not self.host:
                raise ValueError("host is required for remote servers")
            if not self.ssh_username:
                raise ValueError("ssh_username is required for remote servers")
            if not self.ssh_private_key_pem:
                raise ValueError("ssh_private_key_pem is required for remote servers")
        return self


class ServerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    host: str | None = Field(None, max_length=253)
    port: int | None = Field(None, ge=1, le=65535)
    ssh_username: str | None = Field(None, max_length=64)
    ssh_private_key_pem: str | None = None
    sudo_password: str | None = None

    @field_validator("name")
    @classmethod
    def name_safe(cls, v: str | None) -> str | None:
        if v is not None and not _SAFE_NAME_RE.match(v):
            raise ValueError("name must only contain letters, digits, underscores, and hyphens")
        return v


class ServerRead(BaseModel):
    id: int
    name: str
    is_local: bool
    host: str | None
    port: int
    ssh_username: str | None
    ssh_host_fingerprint: str | None
    description: str | None
    has_sudo_password: bool = False

    model_config = {"from_attributes": True}

    @classmethod
    def from_server(cls, server) -> "ServerRead":
        return cls(
            id=server.id,
            name=server.name,
            is_local=server.is_local,
            host=server.host,
            port=server.port,
            ssh_username=server.ssh_username,
            ssh_host_fingerprint=server.ssh_host_fingerprint,
            description=server.description,
            has_sudo_password=server.sudo_password_encrypted_blob is not None,
        )


class ServerTestConnectionResult(BaseModel):
    success: bool
    message: str
    fingerprint: str | None = None
