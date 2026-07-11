from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UserRole(Base, TimestampMixin):
    """One row per role resolved for a user (supports multi-AD-group membership)."""
    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # admin|operator|viewer|vpn_user

    __table_args__ = (UniqueConstraint("user_id", "role", name="uq_user_roles_user_role"),)
