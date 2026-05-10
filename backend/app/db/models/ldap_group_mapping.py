from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class LdapGroupRoleMapping(Base, TimestampMixin):
    """Maps an LDAP/AD group DN to an application role."""
    __tablename__ = "ldap_group_role_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ldap_config_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ldap_configs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_dn: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # admin|operator|viewer|vpn_user

    ldap_config: Mapped["LdapConfig"] = relationship(  # noqa: F821
        "LdapConfig", back_populates="group_role_mappings"
    )
