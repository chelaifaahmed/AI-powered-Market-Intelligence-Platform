"""add source management fields

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f7
Create Date: 2026-03-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

# revision identifiers, used by Alembic.
revision = "b3c4d5e6f7a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_sources", sa.Column("region", sa.String(50), nullable=True, comment="Geographic region: EU, TN, US, Global"))
    op.add_column("review_sources", sa.Column("keywords", ARRAY(sa.Text), nullable=True, comment="Search keywords for this source"))
    op.add_column("review_sources", sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("review_sources", sa.Column("total_records_scraped", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("review_sources", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True, comment="Soft-delete timestamp"))


def downgrade() -> None:
    op.drop_column("review_sources", "deleted_at")
    op.drop_column("review_sources", "total_records_scraped")
    op.drop_column("review_sources", "last_scraped_at")
    op.drop_column("review_sources", "keywords")
    op.drop_column("review_sources", "region")
