"""Add pam_users and pam_groups tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pam_groups",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "server_id",
            sa.Integer,
            sa.ForeignKey("servers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("gid", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_pam_groups_server_id", "pam_groups", ["server_id"])
    op.create_unique_constraint(
        "uq_pam_group_server_name", "pam_groups", ["server_id", "name"]
    )

    op.create_table(
        "pam_users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "server_id",
            sa.Integer,
            sa.ForeignKey("servers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("groups", sa.Text, nullable=True),
        sa.Column("passwd_hash", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_pam_users_server_id", "pam_users", ["server_id"])
    op.create_unique_constraint(
        "uq_pam_user_server_username", "pam_users", ["server_id", "username"]
    )


def downgrade() -> None:
    op.drop_table("pam_users")
    op.drop_table("pam_groups")
