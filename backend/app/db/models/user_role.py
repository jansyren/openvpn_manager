from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UserRole(Base, TimestampMixin):
    """One row per role resolved for a user (supports multi-AD-group membership).

    `source` distinguishes AD-group-derived roles ("ldap", recomputed wholesale on
    every LDAP login) from manually-granted roles ("manual", set via the Users admin
    page) so a manual override survives the next LDAP login instead of being wiped
    out by the group-membership recompute.
    """
    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # admin|operator|viewer|vpn_user
    source: Mapped[str] = mapped_column(String(16), default="ldap", nullable=False, server_default="manual")

    __table_args__ = (
        UniqueConstraint("user_id", "role", "source", name="uq_user_roles_user_role_source"),
    )
