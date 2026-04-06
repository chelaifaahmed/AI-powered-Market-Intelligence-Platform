"""add region field to car_brands and insurance_companies

Revision ID: b2c3d4e5f6a7
Revises: f2a3b4c5d6e7
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("car_brands", sa.Column("region", sa.String(20), nullable=True,
                                          comment="Geographic region code, e.g. TN, EU, Global"))
    op.add_column("insurance_companies", sa.Column("region", sa.String(20), nullable=True,
                                                   comment="Geographic region code, e.g. TN, EU, Global"))
    op.create_index("idx_brands_region", "car_brands", ["region"])
    op.create_index("idx_insurers_region", "insurance_companies", ["region"])


def downgrade() -> None:
    op.drop_index("idx_insurers_region", table_name="insurance_companies")
    op.drop_index("idx_brands_region", table_name="car_brands")
    op.drop_column("insurance_companies", "region")
    op.drop_column("car_brands", "region")
