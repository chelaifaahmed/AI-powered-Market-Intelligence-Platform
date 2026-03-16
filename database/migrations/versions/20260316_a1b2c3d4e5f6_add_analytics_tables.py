"""add_analytics_tables

Revision ID: a1b2c3d4e5f6
Revises: 350d9942b399
Create Date: 2026-03-16

Adds two analytics aggregate tables:
  - brand_reputation_scores   (monthly avg rating + avg sentiment per brand)
  - sentiment_trends          (monthly positive/neutral/negative counts per brand)
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "350d9942b399"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # brand_reputation_scores
    # ------------------------------------------------------------------
    op.create_table(
        "brand_reputation_scores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False,
                  comment="First day of the calendar month this score covers."),
        sa.Column("avg_rating", sa.Numeric(4, 2), nullable=True,
                  comment="Mean star rating (1-5) across all reviews for this brand/period."),
        sa.Column("avg_sentiment_score", sa.Numeric(6, 4), nullable=True,
                  comment="Mean NLP sentiment score (-1.0 to 1.0) for this brand/period."),
        sa.Column("review_count", sa.Integer(), nullable=False,
                  server_default="0",
                  comment="Total number of reviews included in this aggregation."),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Timestamp of the analytics run that produced this row.",
        ),
        sa.CheckConstraint("review_count >= 0", name="chk_brs_review_count"),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["car_brands.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "period_date", name="uq_brs_brand_period"),
        comment="Monthly brand reputation scores — upserted on each analytics run.",
    )
    op.create_index("idx_brs_brand", "brand_reputation_scores", ["brand_id"])
    op.create_index("idx_brs_period", "brand_reputation_scores", ["period_date"])
    op.create_index(
        "idx_brs_brand_period", "brand_reputation_scores", ["brand_id", "period_date"]
    )

    # ------------------------------------------------------------------
    # sentiment_trends
    # ------------------------------------------------------------------
    op.create_table(
        "sentiment_trends",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("positive_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("neutral_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("negative_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_sentiment_score", sa.Numeric(6, 4), nullable=True,
                  comment="Mean NLP sentiment score (-1.0 to 1.0) for this brand/period."),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("positive_count >= 0", name="chk_st_positive"),
        sa.CheckConstraint("neutral_count  >= 0", name="chk_st_neutral"),
        sa.CheckConstraint("negative_count >= 0", name="chk_st_negative"),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["car_brands.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("brand_id", "period_date", name="uq_st_brand_period"),
        comment="Monthly sentiment distribution per brand — upserted on each analytics run.",
    )
    op.create_index("idx_st_brand", "sentiment_trends", ["brand_id"])
    op.create_index("idx_st_period", "sentiment_trends", ["period_date"])
    op.create_index(
        "idx_st_brand_period", "sentiment_trends", ["brand_id", "period_date"]
    )


def downgrade() -> None:
    op.drop_index("idx_st_brand_period", table_name="sentiment_trends")
    op.drop_index("idx_st_period", table_name="sentiment_trends")
    op.drop_index("idx_st_brand", table_name="sentiment_trends")
    op.drop_table("sentiment_trends")

    op.drop_index("idx_brs_brand_period", table_name="brand_reputation_scores")
    op.drop_index("idx_brs_period", table_name="brand_reputation_scores")
    op.drop_index("idx_brs_brand", table_name="brand_reputation_scores")
    op.drop_table("brand_reputation_scores")
