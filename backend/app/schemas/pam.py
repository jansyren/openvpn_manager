import re

from pydantic import BaseModel, Field, field_validator

_UNIX_USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_\-]{0,30}$")


class PamUserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)
    groups: list[str] = Field(default_factory=list)

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if not _UNIX_USERNAME_RE.match(v):
            raise ValueError("Invalid UNIX username format")
        return v

    @field_validator("groups")
    @classmethod
    def groups_valid(cls, v: list[str]) -> list[str]:
        for group in v:
            if not _UNIX_USERNAME_RE.match(group):
                raise ValueError(f"Invalid group name: {group}")
        return v


class PamUserUpdate(BaseModel):
    password: str | None = Field(None, min_length=8, max_length=128)
    groups: list[str] | None = None

    @field_validator("groups")
    @classmethod
    def groups_valid(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for group in v:
                if not re.match(r"^[a-z_][a-z0-9_\-]{0,30}$", group):
                    raise ValueError(f"Invalid group name: {group}")
        return v


class PamUserRead(BaseModel):
    username: str
    groups: list[str]
    uid: int | None = None


class PamGroupRead(BaseModel):
    name: str
    gid: int | None = None
    members: list[str] = Field(default_factory=list)
