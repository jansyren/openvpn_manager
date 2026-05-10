from typing import Literal

from pydantic import BaseModel, Field, model_validator

AppRole = Literal["admin", "operator", "viewer", "vpn_user"]
AuthSource = Literal["local", "ldap"]


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str | None = Field(None, min_length=8, max_length=128)
    role: AppRole = "viewer"
    is_active: bool = True
    auth_source: AuthSource = "local"
    ldap_config_id: int | None = None

    @model_validator(mode="after")
    def password_required_for_local(self) -> "UserCreate":
        if self.auth_source == "local" and not self.password:
            raise ValueError("password is required for local users")
        return self


class UserUpdate(BaseModel):
    password: str | None = Field(None, min_length=8, max_length=128)
    role: AppRole | None = None
    is_active: bool | None = None


class UserManagementRead(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    is_superuser: bool
    auth_source: str

    model_config = {"from_attributes": True}
