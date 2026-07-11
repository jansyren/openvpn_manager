from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # '!ldap' sentinel stored for LDAP users; checked via auth_source before use
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False, server_default="!ldap")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Local "break-glass" superuser flag only; LDAP admins pass authorization via
    # active_role == "admin" instead (see dependencies.get_current_superuser).
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="admin", nullable=False, server_default="admin")
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # LDAP / local auth source
    auth_source: Mapped[str] = mapped_column(String(8), default="local", nullable=False, server_default="local")
    ldap_dn: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ldap_config_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ldap_configs.id", ondelete="SET NULL"), nullable=True
    )
