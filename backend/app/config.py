from functools import lru_cache
from pathlib import Path

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@lru_cache
def _read_pem(path: str) -> str:
    """Read a PEM file once and cache it (keyed on path)."""
    return Path(path).read_text()


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
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    login_rate_limit_per_minute: int = 10

    # Auth lockout
    max_failed_login_attempts: int = 5
    lockout_duration_minutes: int = 10

    # Optional Redis for shared auth state (token blacklist + login lockout).
    # When set, blacklist/lockout are stored in Redis so they survive restarts
    # and are shared across workers/replicas. Unset → in-memory (single worker).
    redis_url: str | None = None

    # Initial admin (created on first startup if set)
    app_admin_username: str | None = None
    app_admin_password: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def validate_and_harden(self) -> "Settings":
        if len(self.app_secret_key) < 32:
            raise ValueError("APP_SECRET_KEY must be at least 32 characters long")
        # SSH_KEY_ENCRYPTION_SECRET roots ALL secret encryption (SSH keys, sudo/CA/
        # LDAP passwords), so it must be present and non-trivial.
        if len(self.ssh_key_encryption_secret) < 32:
            raise ValueError("SSH_KEY_ENCRYPTION_SECRET must be at least 32 characters long")
        # Debug must never be on in production, regardless of how it was set.
        if self.app_env == "production" and self.app_debug:
            self.app_debug = False
        return self

    @property
    def jwt_private_key(self) -> str:
        return _read_pem(str(self.jwt_private_key_path))

    @property
    def jwt_public_key(self) -> str:
        return _read_pem(str(self.jwt_public_key_path))

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
