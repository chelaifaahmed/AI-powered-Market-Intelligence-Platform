"""add_data_origin_to_company_tables

Revision ID: d5e6f7g8h9i0
Revises: c4d5e6f7g8h9
Create Date: 2026-05-14

Adds data_origin VARCHAR(20) DEFAULT 'scraped' to company_action_signals and
company_tech_stack.  All existing rows inherit 'scraped' via server_default;
no UPDATE statements are issued (Option C).
"""

from alembic import op
import sqlalchemy as sa

revision = "d5e6f7g8h9i0"
down_revision = "c4d5e6f7g8h9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "company_action_signals",
        sa.Column(
            "data_origin",
            sa.String(20),
            nullable=False,
            server_default="scraped",
        ),
    )
    op.add_column(
        "company_tech_stack",
        sa.Column(
            "data_origin",
            sa.String(20),
            nullable=False,
            server_default="scraped",
        ),
    )


def downgrade() -> None:
    op.drop_column("company_action_signals", "data_origin")
    op.drop_column("company_tech_stack", "data_origin")
