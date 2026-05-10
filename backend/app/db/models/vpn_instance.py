from sqlalchemy import Boolean, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class VpnInstance(Base, TimestampMixin):
    __tablename__ = "vpn_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    server_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    config_path: Mapped[str] = mapped_column(String(512), nullable=False)
    proto: Mapped[str] = mapped_column(String(8), default="udp", nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=1194, nullable=False)
    dev: Mapped[str] = mapped_column(String(16), default="tun", nullable=False)
    network: Mapped[str | None] = mapped_column(String(18), nullable=True)
    netmask: Mapped[str | None] = mapped_column(String(18), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="unknown", nullable=False)
    easyrsa_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pki_dir: Mapped[str | None] = mapped_column(String(512), nullable=True)
    easyrsa_server_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("servers.id", ondelete="SET NULL"), nullable=True
    )
    pam_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tls_auth_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    easyrsa_use_sudo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    enforce_cn_username: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    ldap_auth_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    ldap_config_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ldap_configs.id", ondelete="SET NULL"), nullable=True
    )
    # AES-256-GCM encrypted CA passphrase (nonce prepended)
    ca_passphrase_encrypted_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    server: Mapped["Server"] = relationship(  # noqa: F821
        "Server", foreign_keys=[server_id], back_populates="vpn_instances"
    )
    clients: Mapped[list["VpnClient"]] = relationship(  # noqa: F821
        "VpnClient", back_populates="vpn_instance", cascade="all, delete-orphan"
    )
    certificates: Mapped[list["Certificate"]] = relationship(  # noqa: F821
        "Certificate", back_populates="vpn_instance", cascade="all, delete-orphan"
    )
