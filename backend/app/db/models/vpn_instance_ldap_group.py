from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class VpnInstanceLdapGroup(Base, TimestampMixin):
    """Associates an LDAP group with a VPN instance for user sync and auth."""
    __tablename__ = "vpn_instance_ldap_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vpn_instance_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vpn_instances.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ldap_config_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ldap_configs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_dn: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    ldap_config: Mapped["LdapConfig"] = relationship(  # noqa: F821
        "LdapConfig", back_populates="vpn_instance_ldap_groups"
    )
