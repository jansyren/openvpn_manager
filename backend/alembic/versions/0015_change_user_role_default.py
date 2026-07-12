"""Change users.role server default from admin to vpn_user

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-12

A user created without an explicit role must default to the lowest-privilege
role, not admin. This alters the column's server default; existing rows are
unchanged (their role was set explicitly at creation).
"""
import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "role", server_default="vpn_user")


def downgrade() -> None:
    op.alter_column("users", "role", server_default="admin")
