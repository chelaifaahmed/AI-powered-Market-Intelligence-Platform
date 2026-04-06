#!/usr/bin/env python3
"""
scripts/seed_tunisia_brands.py
---------------------------------
Seeds Tunisian car concessionnaires (brand distributors) into the database.

These represent the major automotive distributors operating in the Tunisian
market — each is the exclusive importer for one or more international brands.

Usage:
    python scripts/seed_tunisia_brands.py
"""

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from database.connection import get_db_session
from database.models import CarBrand

# ---------------------------------------------------------------------------
# Tunisian concessionnaires (official brand importers)
# ---------------------------------------------------------------------------
TUNISIAN_BRANDS = [
    {"name": "Ennakl (Volkswagen/Audi TN)",  "country_of_origin": "Tunisia", "founded_year": 1963},
    {"name": "Artes (Renault TN)",            "country_of_origin": "Tunisia", "founded_year": 1992},
    {"name": "STAFIM (Peugeot TN)",           "country_of_origin": "Tunisia", "founded_year": 1963},
    {"name": "SATA (Toyota TN)",              "country_of_origin": "Tunisia", "founded_year": 1966},
    {"name": "Sovac (General Motors TN)",     "country_of_origin": "Tunisia", "founded_year": 1970},
    {"name": "ATL (Ford TN)",                 "country_of_origin": "Tunisia", "founded_year": 1976},
]


def seed_tunisian_brands() -> int:
    """Upsert Tunisian car concessionnaires. Returns count of new rows."""
    count = 0
    with get_db_session() as session:
        for b in TUNISIAN_BRANDS:
            existing = session.query(CarBrand).filter(
                CarBrand.name == b["name"]
            ).first()
            if existing:
                existing.country_of_origin = b["country_of_origin"]
                existing.region = "TN"
                existing.founded_year = b["founded_year"]
                print(f"  Updated: {b['name']}")
            else:
                brand = CarBrand(
                    name=b["name"],
                    country_of_origin=b["country_of_origin"],
                    region="TN",
                    founded_year=b["founded_year"],
                    is_active=True,
                )
                session.add(brand)
                count += 1
                print(f"  Created: {b['name']}")
        session.commit()
    return count


def main():
    print("=" * 56)
    print("Seeding Tunisian car concessionnaires")
    print("=" * 56)
    created = seed_tunisian_brands()
    print(f"\nDone — {created} new brands created (region=TN)")
    print("=" * 56)


if __name__ == "__main__":
    main()
