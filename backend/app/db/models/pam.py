from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PamGroup(Base, TimestampMixin):
    __tablename__ = "pam_groups"
    __table_args__ = (UniqueConstraint("server_id", "name", name="uq_pam_group_server_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    server_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    gid: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PamUser(Base, TimestampMixin):
    __tablename__ = "pam_users"
    __table_args__ = (UniqueConstraint("server_id", "username", name="uq_pam_user_server_username"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    server_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    groups: Mapped[str | None] = mapped_column(Text, nullable=True)  # comma-separated
    passwd_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
