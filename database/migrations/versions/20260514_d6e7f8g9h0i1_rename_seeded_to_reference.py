"""rename_seeded_to_reference

Revision ID: d6e7f8g9h0i1
Revises: d5e6f7g8h9i0
Create Date: 2026-05-14

Renames data_origin value 'seeded' → 'reference' across every table that has
a data_origin column.  Also updates column server_defaults so new rows receive
'reference' when inserted without an explicit value.

The rename distinguishes "reference / seed data we loaded for demos" from
real scraped intelligence.  All existing 'scraped' records are untouched.
"""

from alembic import op
import sqlalchemy as sa

revision = "d6e7f8g9h0i1"
down_revision = "d5e6f7g8h9i0"
branch_labels = None
depends_on = None

# Tables whose data_origin column may contain 'seeded'
_TABLES = [
    "car_reviews",
    "insurance_reviews",
    "car_listings",
    "market_trend_articles",
    "competitor_pricings",
    "brand_reputation_scores",
    "sentiment_trends",
    "erp_vendors",
    "teamwill_competitors",
    "teamwill_erp_solutions",
    "company_profile",
    "company_action_signals",
    "company_tech_stack",
]


def upgrade() -> None:
    conn = op.get_bind()
    for table in _TABLES:
        # Rename existing values
        conn.execute(
            sa.text(f"UPDATE {table} SET data_origin = 'reference' WHERE data_origin = 'seeded'")  # noqa: S608
        )
        # Update server_default so future inserts also get 'reference'
        conn.execute(
            sa.text(f"ALTER TABLE {table} ALTER COLUMN data_origin SET DEFAULT 'reference'")
        )


def downgrade() -> None:
    conn = op.get_bind()
    for table in _TABLES:
        conn.execute(
            sa.text(f"UPDATE {table} SET data_origin = 'seeded' WHERE data_origin = 'reference'")  # noqa: S608
        )
        conn.execute(
            sa.text(f"ALTER TABLE {table} ALTER COLUMN data_origin SET DEFAULT 'seeded'")
        )
