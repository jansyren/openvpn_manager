from functools import lru_cache
from pathlib import Path

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_secret_key: str
    app_debug: bool = False

    # JWT
    jwt_private_key_path: Path = Path("./private.pem")
    jwt_public_key_path: Path = Path("./public.pem")
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Database (PostgreSQL required)
    database_url: str

    # SSH key encryption
    ssh_key_encryption_secret: str

    # CORS (comma-separated string in env)
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    # Backup
    backup_storage_path: Path = Path("./backups")
    backup_max_retention_days: int = 30

    # Rate limiting
    rate_limit_per_minute: int = 60
    login_rate_limit_per_minute: int = 10

    # Auth lockout
    max_failed_login_attempts: int = 5
    lockout_duration_minutes: int = 10

    # Initial admin (created on first startup if set)
    app_admin_username: str | None = None
    app_admin_password: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def validate_secret_key_length(self) -> "Settings":
        if len(self.app_secret_key) < 32:
            raise ValueError("APP_SECRET_KEY must be at least 32 characters long")
        return self

    @property
    def jwt_private_key(self) -> str:
        return self.jwt_private_key_path.read_text()

    @property
    def jwt_public_key(self) -> str:
        return self.jwt_public_key_path.read_text()

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
