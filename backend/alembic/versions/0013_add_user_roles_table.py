"""Add user_roles table for multi-role AD/LDAP support

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-11
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "role", name="uq_user_roles_user_role"),
    )
    # Backfill: every existing user gets a row for their current primary role,
    # so behavior is unchanged immediately after migration (no re-login required).
    op.execute(
        "INSERT INTO user_roles (user_id, role, created_at, updated_at) "
        "SELECT id, role, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM users"
    )


def downgrade() -> None:
    op.drop_table("user_roles")
