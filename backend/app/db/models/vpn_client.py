from sqlalchemy import Boolean, ForeignKey, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class VpnClient(Base, TimestampMixin):
    __tablename__ = "vpn_clients"
    __table_args__ = (
        UniqueConstraint("vpn_instance_id", "name", name="uq_vpn_clients_instance_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vpn_instance_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vpn_instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 'user' = user client with embedded certs; 'site' = site with external certs
    client_type: Mapped[str] = mapped_column(String(8), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    # AES-256-GCM encrypted .ovpn file content cached
    config_blob_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    cert_serial: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    vpn_instance: Mapped["VpnInstance"] = relationship(  # noqa: F821
        "VpnInstance", back_populates="clients"
    )
