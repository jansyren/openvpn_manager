import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class PamGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    gid: int | None = None

    @field_validator("name")
    @classmethod
    def name_valid(cls, v: str) -> str:
        if not _UNIX_USERNAME_RE.match(v):
            raise ValueError("Invalid UNIX group name format")
        return v


class StoredPamUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    server_id: int
    username: str
    groups: list[str]
    has_hash: bool


class StoredPamGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    server_id: int
    name: str
    gid: int | None


class PamCopyRequest(BaseModel):
    source_server_id: int
    target_server_id: int
    include_groups: bool = True


class PamCopyResult(BaseModel):
    groups_created: int = 0
    groups_skipped: int = 0
    groups_failed: list[str] = Field(default_factory=list)
    users_created: int = 0
    users_skipped: int = 0
    users_failed: list[str] = Field(default_factory=list)
