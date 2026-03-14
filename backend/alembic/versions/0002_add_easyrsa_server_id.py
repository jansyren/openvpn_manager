"""Add easyrsa_server_id to vpn_instances

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vpn_instances",
        sa.Column("easyrsa_server_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_vpn_instances_easyrsa_server_id",
        "vpn_instances",
        "servers",
        ["easyrsa_server_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_vpn_instances_easyrsa_server_id", "vpn_instances", type_="foreignkey")
    op.drop_column("vpn_instances", "easyrsa_server_id")
