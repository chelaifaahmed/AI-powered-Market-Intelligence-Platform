"""add search keywords table

Revision ID: c5d6e7f8a9b0
Revises: b3c4d5e6f7a8
Create Date: 2026-03-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "c5d6e7f8a9b0"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_keywords",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("keyword", sa.String(200), nullable=False, unique=True),
        sa.Column("region", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_searched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("results_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        comment="Keywords monitored for automated article discovery.",
    )
    op.create_index("idx_sk_active", "search_keywords", ["is_active"], postgresql_where=sa.text("is_active = TRUE"))


def downgrade() -> None:
    op.drop_index("idx_sk_active", table_name="search_keywords")
    op.drop_table("search_keywords")
