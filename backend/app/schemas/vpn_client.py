import re
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-\.]{1,64}$")


class VpnClientCreate(BaseModel):
    vpn_instance_id: int
    name: str = Field(..., min_length=1, max_length=64)
    client_type: Literal["user", "site"]
    email: EmailStr | None = None

    # Certificate generation (required when PKI is configured)
    ca_passphrase: str | None = None
    cert_expire_days: int = Field(825, ge=1, le=9999)

    # PAM user creation (applies when client_type == "user" and not import_existing)
    pam_password: str | None = Field(None, min_length=8, max_length=128)
    pam_groups: list[str] = Field(default_factory=lambda: ["openvpn"])

    # Import mode: verify existing PAM user + import existing PKI cert; skip creation
    import_existing: bool = False
    # When import_existing and client_type == "user": verify a matching PAM account
    # exists before importing. Set False to import a cert-only client (e.g. an
    # app-managed LDAP/local "vpn_user" account with no corresponding PAM user).
    require_pam_user: bool = True

    @field_validator("name")
    @classmethod
    def name_safe(cls, v: str) -> str:
        if not _SAFE_NAME_RE.match(v):
            raise ValueError(
                "Client name must only contain letters, digits, underscores, hyphens, or dots"
            )
        return v


class VpnClientUpdate(BaseModel):
    email: EmailStr | None = None


class VpnClientRevoke(BaseModel):
    ca_passphrase: str | None = None


class VpnClientRead(BaseModel):
    id: int
    vpn_instance_id: int
    name: str
    client_type: str
    email: str | None
    cert_serial: str | None
    is_revoked: bool

    model_config = {"from_attributes": True}


class VpnClientOvpnExport(BaseModel):
    client_id: int
    filename: str
    # content is streamed as a file download; this schema is for metadata only
