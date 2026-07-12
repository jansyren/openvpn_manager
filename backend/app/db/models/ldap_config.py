from sqlalchemy import Boolean, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class LdapConfig(Base, TimestampMixin):
    __tablename__ = "ldap_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    server_url: Mapped[str] = mapped_column(String(256), nullable=False)
    server_url_backup: Mapped[str | None] = mapped_column(String(256), nullable=True)
    bind_dn: Mapped[str] = mapped_column(String(512), nullable=False)
    # AES-256-GCM encrypted bind password
    bind_password_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    user_search_base: Mapped[str] = mapped_column(String(512), nullable=False)
    user_filter: Mapped[str] = mapped_column(String(256), default="(objectClass=user)", nullable=False)
    username_attr: Mapped[str] = mapped_column(String(64), default="sAMAccountName", nullable=False)
    group_search_base: Mapped[str | None] = mapped_column(String(512), nullable=True)
    group_member_attr: Mapped[str] = mapped_column(String(64), default="member", nullable=False)
    use_tls: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tls_verify_cert: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ca_cert_pem: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    group_role_mappings: Mapped[list["LdapGroupRoleMapping"]] = relationship(  # noqa: F821
        "LdapGroupRoleMapping", back_populates="ldap_config", cascade="all, delete-orphan"
    )
    vpn_instance_ldap_groups: Mapped[list["VpnInstanceLdapGroup"]] = relationship(  # noqa: F821
        "VpnInstanceLdapGroup", back_populates="ldap_config", cascade="all, delete-orphan"
    )
