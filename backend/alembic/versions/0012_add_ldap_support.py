"""Add LDAP/AD integration support

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ldap_configs ────────────────────────────────────────────────────────
    op.create_table(
        "ldap_configs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("server_url", sa.String(256), nullable=False),
        sa.Column("server_url_backup", sa.String(256), nullable=True),
        sa.Column("bind_dn", sa.String(512), nullable=False),
        sa.Column("bind_password_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("user_search_base", sa.String(512), nullable=False),
        sa.Column("user_filter", sa.String(256), nullable=False, server_default="(objectClass=user)"),
        sa.Column("username_attr", sa.String(64), nullable=False, server_default="sAMAccountName"),
        sa.Column("group_search_base", sa.String(512), nullable=True),
        sa.Column("group_member_attr", sa.String(64), nullable=False, server_default="member"),
        sa.Column("use_tls", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("tls_verify_cert", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("ca_cert_pem", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── ldap_group_role_mappings ─────────────────────────────────────────────
    op.create_table(
        "ldap_group_role_mappings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("ldap_config_id", sa.Integer(), sa.ForeignKey("ldap_configs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("group_dn", sa.String(512), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── vpn_instance_ldap_groups ─────────────────────────────────────────────
    op.create_table(
        "vpn_instance_ldap_groups",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("vpn_instance_id", sa.Integer(), sa.ForeignKey("vpn_instances.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("ldap_config_id", sa.Integer(), sa.ForeignKey("ldap_configs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("group_dn", sa.String(512), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── users: add auth_source, ldap_dn, ldap_config_id ────────────────────
    op.add_column("users", sa.Column("auth_source", sa.String(8), nullable=False, server_default="local"))
    op.add_column("users", sa.Column("ldap_dn", sa.String(512), nullable=True))
    op.add_column("users", sa.Column("ldap_config_id", sa.Integer(), sa.ForeignKey("ldap_configs.id", ondelete="SET NULL"), nullable=True))

    # ── vpn_instances: add ldap_auth_enabled, ldap_config_id ───────────────
    op.add_column("vpn_instances", sa.Column("ldap_auth_enabled", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("vpn_instances", sa.Column("ldap_config_id", sa.Integer(), sa.ForeignKey("ldap_configs.id", ondelete="SET NULL"), nullable=True))


def downgrade() -> None:
    op.drop_column("vpn_instances", "ldap_config_id")
    op.drop_column("vpn_instances", "ldap_auth_enabled")
    op.drop_column("users", "ldap_config_id")
    op.drop_column("users", "ldap_dn")
    op.drop_column("users", "auth_source")
    op.drop_table("vpn_instance_ldap_groups")
    op.drop_table("ldap_group_role_mappings")
    op.drop_table("ldap_configs")
