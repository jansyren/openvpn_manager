import ipaddress
import re

from pydantic import BaseModel, Field, field_validator

_TUN_RE = re.compile(r"^tun\d+$")


class RouteBase(BaseModel):
    source_tun: str = Field(..., max_length=16)
    dest_tun: str = Field(..., max_length=16)
    destination_network: str  # CIDR e.g. 10.8.1.0/24
    metric: int = Field(0, ge=0)
    is_persistent: bool = True

    @field_validator("source_tun", "dest_tun")
    @classmethod
    def tun_name_valid(cls, v: str) -> str:
        if not _TUN_RE.match(v):
            raise ValueError("tun interface name must be in the form tunN (e.g. tun0)")
        return v

    @field_validator("destination_network")
    @classmethod
    def network_valid(cls, v: str) -> str:
        try:
            ipaddress.IPv4Network(v, strict=False)
        except ValueError as exc:
            raise ValueError(f"Invalid IPv4 network: {v}") from exc
        return v


class RouteCreate(RouteBase):
    server_id: int


class RouteUpdate(BaseModel):
    metric: int | None = Field(None, ge=0)
    is_persistent: bool | None = None


class RouteRead(BaseModel):
    id: int
    server_id: int
    source_tun: str
    dest_tun: str
    destination_network: str
    metric: int
    is_persistent: bool
    is_active: bool

    model_config = {"from_attributes": True}


class LiveRoutingTable(BaseModel):
    server_id: int
    routes: list[str]  # raw lines from `ip route show`
