from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    # refresh token sent via cookie; this body is empty but kept for extensibility
    pass


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=12, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserRead(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    is_superuser: bool
    roles: list[str]
    active_role: str

    model_config = {"from_attributes": True}


class SwitchRoleRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=16)
