import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")
_SAFE_PATH_RE = re.compile(r"^(/[a-zA-Z0-9_\-\.]+)+\.conf$")


class VpnInstanceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    config_path: str
    proto: Literal["udp", "tcp"] = "udp"
    port: int = Field(1194, ge=1, le=65535)
    dev: str = Field("tun", max_length=16)
    network: str | None = None
    netmask: str | None = None
    easyrsa_path: str | None = None
    easyrsa_server_id: int | None = None
    pam_enabled: bool = False

    @field_validator("name")
    @classmethod
    def name_safe(cls, v: str) -> str:
        if not _SAFE_NAME_RE.match(v):
            raise ValueError("name must only contain letters, digits, underscores, and hyphens")
        return v

    @field_validator("config_path")
    @classmethod
    def config_path_safe(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("config_path must not contain '..'")
        if not _SAFE_PATH_RE.match(v):
            raise ValueError("config_path must be an absolute path ending in .conf")
        return v

    @field_validator("easyrsa_path")
    @classmethod
    def easyrsa_path_safe(cls, v: str | None) -> str | None:
        if v is not None and ".." in v:
            raise ValueError("easyrsa_path must not contain '..'")
        return v


class VpnInstanceCreate(VpnInstanceBase):
    server_id: int


class VpnInstanceUpdate(BaseModel):
    name: str | None = None
    proto: Literal["udp", "tcp"] | None = None
    port: int | None = Field(None, ge=1, le=65535)
    dev: str | None = None
    network: str | None = None
    netmask: str | None = None
    easyrsa_path: str | None = None
    easyrsa_server_id: int | None = None
    pam_enabled: bool | None = None
    tls_auth_key: str | None = None


class VpnInstanceRead(BaseModel):
    id: int
    server_id: int
    name: str
    config_path: str
    proto: str
    port: int
    dev: str
    network: str | None
    netmask: str | None
    status: str
    easyrsa_path: str | None
    easyrsa_server_id: int | None
    pam_enabled: bool
    tls_auth_key: str | None

    model_config = {"from_attributes": True}


class VpnInstanceStatus(BaseModel):
    instance_id: int
    name: str
    status: str  # running | stopped | failed | activating | unknown
    active_since: str | None = None
    pid: int | None = None


class ServiceActionRequest(BaseModel):
    action: Literal["start", "stop", "restart", "reload", "enable", "disable"]


class DiscoveredConfig(BaseModel):
    path: str
    name: str
    size_bytes: int
