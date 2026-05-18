"""v2_opportunity_scorer — add v2_* columns to opportunity_signals

Adds eight new columns to opportunity_signals for the V2 four-axis scorer:
  v2_pain_score, v2_recovery_score, v2_erp_fit_score, v2_reachability_score,
  v2_overall_score, v2_tier, v2_reasoning (JSONB), v2_computed_at.

V1 columns are untouched.  V2 columns are nullable so existing rows are not
broken by the migration.

Revises: b3c4d5e6f7g8  (v2_opportunity_radar tables)
Revision ID: c4d5e6f7g8h9
Created: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c4d5e6f7g8h9"
down_revision = "b3c4d5e6f7g8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "opportunity_signals",
        sa.Column("v2_pain_score", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "opportunity_signals",
        sa.Column("v2_recovery_score", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "opportunity_signals",
        sa.Column("v2_erp_fit_score", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "opportunity_signals",
        sa.Column("v2_reachability_score", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "opportunity_signals",
        sa.Column("v2_overall_score", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "opportunity_signals",
        sa.Column("v2_tier", sa.String(30), nullable=True),
    )
    op.add_column(
        "opportunity_signals",
        sa.Column("v2_reasoning", postgresql.JSONB, nullable=True),
    )
    op.add_column(
        "opportunity_signals",
        sa.Column("v2_computed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("idx_opp_v2_tier", "opportunity_signals", ["v2_tier"])
    op.create_index(
        "idx_opp_v2_overall",
        "opportunity_signals",
        [sa.text("v2_overall_score DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_opp_v2_overall", table_name="opportunity_signals")
    op.drop_index("idx_opp_v2_tier", table_name="opportunity_signals")
    op.drop_column("opportunity_signals", "v2_computed_at")
    op.drop_column("opportunity_signals", "v2_reasoning")
    op.drop_column("opportunity_signals", "v2_tier")
    op.drop_column("opportunity_signals", "v2_overall_score")
    op.drop_column("opportunity_signals", "v2_reachability_score")
    op.drop_column("opportunity_signals", "v2_erp_fit_score")
    op.drop_column("opportunity_signals", "v2_recovery_score")
    op.drop_column("opportunity_signals", "v2_pain_score")
