"""Add easyrsa_use_sudo to vpn_instances

Revision ID: 0004
Revises: 0003
Create Date: 2024-01-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vpn_instances",
        sa.Column("easyrsa_use_sudo", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("vpn_instances", "easyrsa_use_sudo")
