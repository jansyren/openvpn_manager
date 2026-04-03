from sqlalchemy import Boolean, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Server(Base, TimestampMixin):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    is_local: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    host: Mapped[str | None] = mapped_column(String(253), nullable=True)
    port: Mapped[int] = mapped_column(Integer, default=22, nullable=False)
    ssh_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # AES-256-GCM encrypted private key bytes (nonce prepended)
    ssh_key_encrypted_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # AES-256-GCM encrypted sudo password (nonce prepended)
    sudo_password_encrypted_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # SHA-256 fingerprint of the server's SSH host key for TOFU
    ssh_host_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    vpn_instances: Mapped[list["VpnInstance"]] = relationship(  # noqa: F821
        "VpnInstance",
        foreign_keys="VpnInstance.server_id",
        back_populates="server",
        cascade="all, delete-orphan",
    )
    routes: Mapped[list["Route"]] = relationship(  # noqa: F821
        "Route", back_populates="server", cascade="all, delete-orphan"
    )
    backups: Mapped[list["Backup"]] = relationship(  # noqa: F821
        "Backup", back_populates="server"
    )
