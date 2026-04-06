"""Add data_origin to brand_reputation_scores and sentiment_trends.

Allows provenance-aware analytics: separate aggregates for
seeded vs scraped reviews so live intelligence is not contaminated.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- brand_reputation_scores ---
    op.add_column(
        "brand_reputation_scores",
        sa.Column(
            "data_origin",
            sa.String(20),
            nullable=False,
            server_default="all",
            comment="Provenance filter used for this aggregation: all | seeded | scraped",
        ),
    )
    # Drop old unique constraint and create new one including data_origin
    op.drop_constraint("uq_brs_brand_period", "brand_reputation_scores", type_="unique")
    op.create_unique_constraint(
        "uq_brs_brand_period_origin",
        "brand_reputation_scores",
        ["brand_id", "period_date", "data_origin"],
    )
    op.create_index("idx_brs_origin", "brand_reputation_scores", ["data_origin"])

    # --- sentiment_trends ---
    op.add_column(
        "sentiment_trends",
        sa.Column(
            "data_origin",
            sa.String(20),
            nullable=False,
            server_default="all",
            comment="Provenance filter used for this aggregation: all | seeded | scraped",
        ),
    )
    op.drop_constraint("uq_st_brand_period", "sentiment_trends", type_="unique")
    op.create_unique_constraint(
        "uq_st_brand_period_origin",
        "sentiment_trends",
        ["brand_id", "period_date", "data_origin"],
    )
    op.create_index("idx_st_origin", "sentiment_trends", ["data_origin"])


def downgrade() -> None:
    # --- sentiment_trends ---
    op.drop_index("idx_st_origin", table_name="sentiment_trends")
    op.drop_constraint("uq_st_brand_period_origin", "sentiment_trends", type_="unique")
    op.create_unique_constraint(
        "uq_st_brand_period", "sentiment_trends", ["brand_id", "period_date"]
    )
    op.drop_column("sentiment_trends", "data_origin")

    # --- brand_reputation_scores ---
    op.drop_index("idx_brs_origin", table_name="brand_reputation_scores")
    op.drop_constraint(
        "uq_brs_brand_period_origin", "brand_reputation_scores", type_="unique"
    )
    op.create_unique_constraint(
        "uq_brs_brand_period", "brand_reputation_scores", ["brand_id", "period_date"]
    )
    op.drop_column("brand_reputation_scores", "data_origin")
