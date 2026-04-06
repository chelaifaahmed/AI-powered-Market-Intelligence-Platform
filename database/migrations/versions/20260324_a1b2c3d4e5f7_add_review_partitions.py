"""add car_reviews and insurance_reviews partitions

Revision ID: a1b2c3d4e5f7
Revises: c4d5e6f7a8b9
Create Date: 2026-03-24
"""
from alembic import op

revision = "a1b2c3d4e5f7"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    # car_reviews partitions
    for year in (2024, 2025, 2026, 2027):
        op.execute(
            f"CREATE TABLE IF NOT EXISTS car_reviews_{year} "
            f"PARTITION OF car_reviews "
            f"FOR VALUES FROM ('{year}-01-01') TO ('{year + 1}-01-01')"
        )
    op.execute(
        "CREATE TABLE IF NOT EXISTS car_reviews_default "
        "PARTITION OF car_reviews DEFAULT"
    )

    # insurance_reviews partitions
    for year in (2024, 2025, 2026, 2027):
        op.execute(
            f"CREATE TABLE IF NOT EXISTS insurance_reviews_{year} "
            f"PARTITION OF insurance_reviews "
            f"FOR VALUES FROM ('{year}-01-01') TO ('{year + 1}-01-01')"
        )
    op.execute(
        "CREATE TABLE IF NOT EXISTS insurance_reviews_default "
        "PARTITION OF insurance_reviews DEFAULT"
    )


def downgrade():
    for tbl in ("car_reviews", "insurance_reviews"):
        for suffix in ("2024", "2025", "2026", "2027", "default"):
            op.execute(f"DROP TABLE IF EXISTS {tbl}_{suffix}")
