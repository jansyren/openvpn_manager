import re

from pydantic import BaseModel, Field, field_validator

_SAFE_PATH_RE = re.compile(r"^(/[a-zA-Z0-9_\-\.]+)+$")


class EasyRsaPathUpdate(BaseModel):
    easyrsa_path: str

    @field_validator("easyrsa_path")
    @classmethod
    def path_safe(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("path must not contain '..'")
        if not _SAFE_PATH_RE.match(v):
            raise ValueError("path must be a valid absolute path")
        return v


class EasyRsaServerUpdate(BaseModel):
    easyrsa_server_id: int | None = None


class EasyRsaPkiDirUpdate(BaseModel):
    pki_dir: str

    @field_validator("pki_dir")
    @classmethod
    def path_safe(cls, v: str) -> str:
        if ".." in v:
            raise ValueError("path must not contain '..'")
        if not _SAFE_PATH_RE.match(v):
            raise ValueError("path must be a valid absolute path")
        return v


class EasyRsaSudoUpdate(BaseModel):
    easyrsa_use_sudo: bool


class EasyRsaSettings(BaseModel):
    easyrsa_path: str | None
    pki_dir: str | None
    easyrsa_server_id: int | None = None
    easyrsa_use_sudo: bool = False
    pki_initialized: bool
    ca_built: bool
    permission_error: bool = False
    error_detail: str | None = None


class EasyRsaInitPki(BaseModel):
    force: bool = False


class EasyRsaBuildCa(BaseModel):
    # CA passphrase; handled securely in service layer (never logged)
    passphrase: str = Field(..., min_length=4, max_length=128)
    common_name: str = Field("Easy-RSA CA", max_length=64)
    expire_days: int = Field(3650, ge=1, le=9999)


class EasyRsaRenewCa(BaseModel):
    ca_passphrase: str = Field(..., min_length=1)
    expire_days: int = Field(3650, ge=1, le=9999)


class EasyRsaCrossSign(BaseModel):
    new_ca_csr_pem: str = Field(..., min_length=10)
    old_ca_passphrase: str = Field(..., min_length=1)
    expire_days: int = Field(365, ge=1, le=9999)


class EasyRsaBuildServer(BaseModel):
    common_name: str = Field(..., min_length=1, max_length=64)
    passphrase: str | None = None
    expire_days: int = Field(3650, ge=1, le=9999)

    @field_validator("common_name")
    @classmethod
    def cn_safe(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_\-\.]{1,64}$", v):
            raise ValueError("common_name contains invalid characters")
        return v
