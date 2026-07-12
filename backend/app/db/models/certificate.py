from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Certificate(Base, TimestampMixin):
    __tablename__ = "certificates"
    __table_args__ = (
        UniqueConstraint("vpn_instance_id", "serial", name="uq_certificates_instance_serial"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vpn_instance_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vpn_instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    common_name: Mapped[str] = mapped_column(String(64), nullable=False)
    serial: Mapped[str] = mapped_column(String(64), nullable=False)
    # 'ca' | 'server' | 'client'
    cert_type: Mapped[str] = mapped_column(String(8), nullable=False)
    not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    not_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    vpn_instance: Mapped["VpnInstance"] = relationship(  # noqa: F821
        "VpnInstance", back_populates="certificates"
    )
