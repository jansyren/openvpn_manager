"""Add uniqueness constraints to vpn_clients and certificates

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-12

Makes the LDAP-sync "create if absent" logic idempotent under concurrency:
a VPN client name is unique per instance, and a certificate serial is unique
per instance.
"""
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_vpn_clients_instance_name", "vpn_clients", ["vpn_instance_id", "name"]
    )
    op.create_unique_constraint(
        "uq_certificates_instance_serial", "certificates", ["vpn_instance_id", "serial"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_certificates_instance_serial", "certificates", type_="unique")
    op.drop_constraint("uq_vpn_clients_instance_name", "vpn_clients", type_="unique")
