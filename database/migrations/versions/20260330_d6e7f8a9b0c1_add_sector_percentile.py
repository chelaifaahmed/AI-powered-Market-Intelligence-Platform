"""add sector_percentile to opportunity_signals

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "opportunity_signals",
        sa.Column(
            "sector_percentile",
            sa.SmallInteger(),
            nullable=True,
            comment="Distress percentile within sector (0-100). 100 = most distressed.",
        ),
    )


def downgrade() -> None:
    op.drop_column("opportunity_signals", "sector_percentile")
