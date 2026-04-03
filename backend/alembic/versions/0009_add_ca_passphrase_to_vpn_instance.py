"""Add ca_passphrase_encrypted_blob to vpn_instances

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vpn_instances",
        sa.Column("ca_passphrase_encrypted_blob", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vpn_instances", "ca_passphrase_encrypted_blob")
