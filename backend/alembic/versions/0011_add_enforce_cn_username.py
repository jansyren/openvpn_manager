"""add enforce_cn_username to vpn_instances

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vpn_instances",
        sa.Column(
            "enforce_cn_username",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("vpn_instances", "enforce_cn_username")
