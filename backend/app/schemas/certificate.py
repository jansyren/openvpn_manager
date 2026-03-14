from datetime import datetime

from pydantic import BaseModel, Field


class CertificateRead(BaseModel):
    id: int
    vpn_instance_id: int
    common_name: str
    serial: str
    cert_type: str
    not_before: datetime | None
    not_after: datetime | None
    is_revoked: bool
    revoked_at: datetime | None
    revoke_reason: str | None

    model_config = {"from_attributes": True}


class CertificateRevoke(BaseModel):
    reason: str = Field(
        "unspecified",
        pattern="^(unspecified|keyCompromise|CACompromise|affiliationChanged|superseded|cessationOfOperation|certificateHold)$",
    )
    ca_passphrase: str | None = None


class CertificateRenew(BaseModel):
    ca_passphrase: str = Field(..., min_length=1)
    expire_days: int = Field(825, ge=1, le=9999)
