"""add opportunity_signals table

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "c4d5e6f7a8b9"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "opportunity_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("entity_name", sa.String(200), nullable=False),
        sa.Column("region", sa.String(20), nullable=True),
        sa.Column("overall_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("complaint_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("sentiment_drop_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("review_volume_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("top_complaint_types", ARRAY(sa.String), nullable=True),
        sa.Column("score_reasoning", JSONB, nullable=True),
        sa.Column("signal_strength", sa.String(20), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("entity_type", "entity_id", name="uq_oppsig_entity"),
        sa.CheckConstraint("overall_score BETWEEN 0 AND 100", name="chk_oppsig_overall"),
        sa.CheckConstraint("complaint_score BETWEEN 0 AND 100", name="chk_oppsig_complaint"),
        sa.CheckConstraint("sentiment_drop_score BETWEEN 0 AND 100", name="chk_oppsig_sentiment"),
        sa.CheckConstraint("review_volume_score BETWEEN 0 AND 100", name="chk_oppsig_volume"),
        comment="Opportunity scores for TEAMWILL sales targeting - higher = more likely to need ERP.",
    )
    op.create_index(
        "idx_oppsig_type_score", "opportunity_signals",
        ["entity_type", sa.text("overall_score DESC")],
    )
    op.create_index("idx_oppsig_region", "opportunity_signals", ["region"])
    op.create_index("idx_oppsig_strength", "opportunity_signals", ["signal_strength"])


def downgrade() -> None:
    op.drop_index("idx_oppsig_strength", table_name="opportunity_signals")
    op.drop_index("idx_oppsig_region", table_name="opportunity_signals")
    op.drop_index("idx_oppsig_type_score", table_name="opportunity_signals")
    op.drop_table("opportunity_signals")
