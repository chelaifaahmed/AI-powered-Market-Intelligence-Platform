"""add_data_origin_provenance

Revision ID: e1f2a3b4c5d6
Revises: d7e8f9a0b1c2
Create Date: 2026-03-18

Adds a data_origin column to the five main domain tables so that seeded
demo data can be distinguished from records produced by real scraping or
external import.

Valid values:  seeded | scraped | imported
Default:       seeded   (so existing rows are correctly labelled)
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = [
    "car_reviews",
    "insurance_reviews",
    "car_listings",
    "market_trend_articles",
    "competitor_pricings",
]

_CHECK_CONSTRAINT = "data_origin IN ('seeded', 'scraped', 'imported')"


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "data_origin",
                sa.String(20),
                nullable=False,
                server_default="seeded",
            ),
        )
        op.create_check_constraint(
            f"chk_{table}_data_origin",
            table,
            _CHECK_CONSTRAINT,
        )
        op.create_index(
            f"idx_{table}_data_origin",
            table,
            ["data_origin"],
        )
    # All pre-existing rows are explicitly seeded — the server_default handles it,
    # but run an explicit UPDATE for any rows inserted before this migration.
    conn = op.get_bind()
    for table in _TABLES:
        conn.execute(sa.text(f"UPDATE {table} SET data_origin = 'seeded' WHERE data_origin IS NULL"))  # noqa: S608


def downgrade() -> None:
    for table in _TABLES:
        op.drop_index(f"idx_{table}_data_origin", table_name=table)
        op.drop_constraint(f"chk_{table}_data_origin", table, type_="check")
        op.drop_column(table, "data_origin")
