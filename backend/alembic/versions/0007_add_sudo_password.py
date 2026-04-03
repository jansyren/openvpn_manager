"""Add sudo_password_encrypted_blob to servers

Revision ID: 0007
Revises: 0006
Create Date: 2024-01-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("servers", sa.Column("sudo_password_encrypted_blob", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    op.drop_column("servers", "sudo_password_encrypted_blob")
