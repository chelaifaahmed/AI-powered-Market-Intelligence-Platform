"""enrich_vehicle_and_article_fields

Revision ID: d7e8f9a0b1c2
Revises: c3d4e5f6a7b8
Create Date: 2026-03-16

Adds richer structured fields to:
  - car_models      : trim_level, transmission, drivetrain, horsepower_hp,
                      torque_nm, battery_kwh, range_km, doors, seats, msrp_eur
  - car_listings    : fuel_type, transmission, color, trim_level, listing_year
  - market_trend_articles : category, region
  - car_reviews     : pros, cons, variant_tested
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # car_models — vehicle specification fields
    # ------------------------------------------------------------------
    op.add_column("car_models", sa.Column("trim_level",    sa.String(100),  nullable=True))
    op.add_column("car_models", sa.Column("transmission",  sa.String(50),   nullable=True))
    op.add_column("car_models", sa.Column("drivetrain",    sa.String(50),   nullable=True))
    op.add_column("car_models", sa.Column("horsepower_hp", sa.SmallInteger, nullable=True))
    op.add_column("car_models", sa.Column("torque_nm",     sa.SmallInteger, nullable=True))
    op.add_column("car_models", sa.Column("battery_kwh",   sa.Numeric(6, 2),nullable=True))
    op.add_column("car_models", sa.Column("range_km",      sa.SmallInteger, nullable=True))
    op.add_column("car_models", sa.Column("doors",         sa.SmallInteger, nullable=True))
    op.add_column("car_models", sa.Column("seats",         sa.SmallInteger, nullable=True))
    op.add_column("car_models", sa.Column("msrp_eur",      sa.Numeric(12, 2),nullable=True))

    op.create_index("idx_models_transmission", "car_models", ["transmission"])
    op.create_index("idx_models_drivetrain",   "car_models", ["drivetrain"])
    op.create_index("idx_models_hp",           "car_models", ["horsepower_hp"])

    # ------------------------------------------------------------------
    # car_listings — richer listing detail
    # ------------------------------------------------------------------
    op.add_column("car_listings", sa.Column("fuel_type",    sa.String(50),  nullable=True))
    op.add_column("car_listings", sa.Column("transmission", sa.String(50),  nullable=True))
    op.add_column("car_listings", sa.Column("color",        sa.String(50),  nullable=True))
    op.add_column("car_listings", sa.Column("trim_level",   sa.String(100), nullable=True))
    op.add_column("car_listings", sa.Column("listing_year", sa.SmallInteger,nullable=True))

    op.create_index("idx_listings_fuel",         "car_listings", ["fuel_type"])
    op.create_index("idx_listings_color",        "car_listings", ["color"])
    op.create_index("idx_listings_listing_year", "car_listings", ["listing_year"])

    # ------------------------------------------------------------------
    # market_trend_articles — content classification
    # ------------------------------------------------------------------
    op.add_column("market_trend_articles", sa.Column("category", sa.String(60),  nullable=True))
    op.add_column("market_trend_articles", sa.Column("region",   sa.String(100), nullable=True))

    op.create_index("idx_mta_category", "market_trend_articles", ["category"])
    op.create_index("idx_mta_region",   "market_trend_articles", ["region"])

    # ------------------------------------------------------------------
    # car_reviews — editorial detail fields
    # Note: car_reviews is RANGE-partitioned; ALTER TABLE propagates to
    #       all child partitions automatically in PostgreSQL 11+.
    # ------------------------------------------------------------------
    op.add_column("car_reviews", sa.Column("pros",           sa.Text, nullable=True))
    op.add_column("car_reviews", sa.Column("cons",           sa.Text, nullable=True))
    op.add_column("car_reviews", sa.Column("variant_tested", sa.String(200), nullable=True))


def downgrade() -> None:
    # car_reviews
    op.drop_column("car_reviews", "variant_tested")
    op.drop_column("car_reviews", "cons")
    op.drop_column("car_reviews", "pros")

    # market_trend_articles
    op.drop_index("idx_mta_region",   table_name="market_trend_articles")
    op.drop_index("idx_mta_category", table_name="market_trend_articles")
    op.drop_column("market_trend_articles", "region")
    op.drop_column("market_trend_articles", "category")

    # car_listings
    op.drop_index("idx_listings_listing_year", table_name="car_listings")
    op.drop_index("idx_listings_color",        table_name="car_listings")
    op.drop_index("idx_listings_fuel",         table_name="car_listings")
    op.drop_column("car_listings", "listing_year")
    op.drop_column("car_listings", "trim_level")
    op.drop_column("car_listings", "color")
    op.drop_column("car_listings", "transmission")
    op.drop_column("car_listings", "fuel_type")

    # car_models
    op.drop_index("idx_models_hp",           table_name="car_models")
    op.drop_index("idx_models_drivetrain",   table_name="car_models")
    op.drop_index("idx_models_transmission", table_name="car_models")
    op.drop_column("car_models", "msrp_eur")
    op.drop_column("car_models", "seats")
    op.drop_column("car_models", "doors")
    op.drop_column("car_models", "range_km")
    op.drop_column("car_models", "battery_kwh")
    op.drop_column("car_models", "torque_nm")
    op.drop_column("car_models", "horsepower_hp")
    op.drop_column("car_models", "drivetrain")
    op.drop_column("car_models", "transmission")
    op.drop_column("car_models", "trim_level")
