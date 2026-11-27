"""Initial schema: CRM read-only mirror, staff directory and the caliber library.

Revision ID: 0001
Revises:
Create Date: 2026-11-27
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_enterprises",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("uscc", sa.String(32), nullable=True),
        sa.Column("contact_phone", sa.String(32), nullable=True),
        sa.Column("owner_staff_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("industry", sa.String(120), nullable=True),
        sa.Column("track", sa.String(120), nullable=True),
        sa.Column("stage", sa.String(40), nullable=True),
        sa.Column("registered_location", sa.String(120), nullable=True),
        sa.Column("business_summary", sa.Text(), nullable=True),
    )
    op.create_index("ix_crm_enterprises_org_id", "crm_enterprises", ["org_id"])
    op.create_index("ix_crm_enterprises_site_id", "crm_enterprises", ["site_id"])
    op.create_index(
        "ix_crm_enterprises_site_owner", "crm_enterprises", ["site_id", "owner_staff_id"]
    )
    op.create_index("ix_crm_enterprises_site_active", "crm_enterprises", ["site_id", "deleted_at"])

    op.create_table(
        "crm_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "enterprise_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_enterprises.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("job_title", sa.String(120), nullable=True),
        sa.Column("decision_role", sa.String(60), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_crm_contacts_org_id", "crm_contacts", ["org_id"])
    op.create_index("ix_crm_contacts_site_id", "crm_contacts", ["site_id"])
    op.create_index("ix_crm_contacts_enterprise", "crm_contacts", ["enterprise_id"])

    op.create_table(
        "crm_capability_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "enterprise_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_enterprises.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("card_key", sa.String(64), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_crm_capability_cards_org_id", "crm_capability_cards", ["org_id"])
    op.create_index("ix_crm_capability_cards_site_id", "crm_capability_cards", ["site_id"])
    op.create_index("ix_crm_capability_cards_enterprise", "crm_capability_cards", ["enterprise_id"])

    op.create_table(
        "crm_staff",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("role", sa.String(40), nullable=False, server_default="member_manager"),
    )
    op.create_index("ix_crm_staff_org_id", "crm_staff", ["org_id"])
    op.create_index("ix_crm_staff_site_id", "crm_staff", ["site_id"])

    op.create_table(
        "caliber_field_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.String(16), nullable=False),
        sa.Column("fields", postgresql.JSONB(), nullable=False),
        sa.Column("labels", postgresql.JSONB(), nullable=False),
        sa.Column("target_pct", sa.Float(), nullable=False, server_default="95"),
        sa.Column("low_pct", sa.Float(), nullable=False, server_default="80"),
        sa.Column("fresh_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("calc_refs", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_caliber_field_versions_org_id", "caliber_field_versions", ["org_id"])
    op.create_index("ix_caliber_field_versions_site_id", "caliber_field_versions", ["site_id"])
    op.create_index(
        "ix_caliber_field_versions_site_version",
        "caliber_field_versions",
        ["site_id", "version"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("caliber_field_versions")
    op.drop_table("crm_staff")
    op.drop_table("crm_capability_cards")
    op.drop_table("crm_contacts")
    op.drop_table("crm_enterprises")
