"""Add source column to user_roles for manual role overrides

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows predate the ldap/manual distinction; tag them "manual" so nobody
    # loses access immediately after this migration runs (self-heals to "ldap" for
    # AD-derived roles on that user's next LDAP login).
    op.add_column(
        "user_roles",
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
    )
    op.drop_constraint("uq_user_roles_user_role", "user_roles", type_="unique")
    op.create_unique_constraint(
        "uq_user_roles_user_role_source", "user_roles", ["user_id", "role", "source"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_user_roles_user_role_source", "user_roles", type_="unique")
    op.create_unique_constraint("uq_user_roles_user_role", "user_roles", ["user_id", "role"])
    op.drop_column("user_roles", "source")
