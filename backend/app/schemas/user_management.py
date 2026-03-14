from typing import Literal
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)
    role: Literal["admin", "operator", "viewer"] = "viewer"
    is_active: bool = True


class UserUpdate(BaseModel):
    password: str | None = Field(None, min_length=8, max_length=128)
    role: Literal["admin", "operator", "viewer"] | None = None
    is_active: bool | None = None


class UserManagementRead(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    is_superuser: bool

    model_config = {"from_attributes": True}
