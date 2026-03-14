"""Add tls_auth_key to vpn_instances

Revision ID: 0005
Revises: 0004
Create Date: 2024-01-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vpn_instances",
        sa.Column("tls_auth_key", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vpn_instances", "tls_auth_key")
