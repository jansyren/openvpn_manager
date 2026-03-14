from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Route(Base, TimestampMixin):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    server_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_tun: Mapped[str] = mapped_column(String(16), nullable=False)
    dest_tun: Mapped[str] = mapped_column(String(16), nullable=False)
    # CIDR notation e.g. 10.8.1.0/24
    destination_network: Mapped[str] = mapped_column(String(43), nullable=False)
    metric: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_persistent: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    server: Mapped["Server"] = relationship("Server", back_populates="routes")  # noqa: F821
