#!/usr/bin/env python3
"""
scripts/seed_global_brands.py
-------------------------------
Seeds EU insurance companies and car brands for global scraping coverage.

Usage:
    python scripts/seed_global_brands.py
"""

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from database.connection import get_db_session
from database.models import InsuranceCompany, CarBrand

# ---------------------------------------------------------------------------
# EU insurance companies
# ---------------------------------------------------------------------------
EU_INSURERS = [
    {"name": "AXA",         "country": "France",  "website": "https://www.axa.com"},
    {"name": "Allianz",     "country": "Germany", "website": "https://www.allianz.com"},
    {"name": "MAIF",        "country": "France",  "website": "https://www.maif.fr"},
    {"name": "Direct Line", "country": "UK",      "website": "https://www.directline.com"},
    {"name": "Admiral",     "country": "UK",      "website": "https://www.admiral.com"},
    {"name": "Aviva",       "country": "UK",      "website": "https://www.aviva.com"},
    {"name": "Generali",    "country": "Italy",   "website": "https://www.generali.com"},
]

# ---------------------------------------------------------------------------
# EU car brands
# ---------------------------------------------------------------------------
EU_CAR_BRANDS = [
    {"name": "Renault",    "country_of_origin": "France",  "founded_year": 1899},
    {"name": "Peugeot",    "country_of_origin": "France",  "founded_year": 1810},
    {"name": "Volkswagen", "country_of_origin": "Germany", "founded_year": 1937},
    {"name": "BMW",        "country_of_origin": "Germany", "founded_year": 1916},
]


def seed_eu_insurers() -> int:
    """Upsert EU insurance companies. Returns count of new rows."""
    count = 0
    with get_db_session() as session:
        for ins in EU_INSURERS:
            existing = session.query(InsuranceCompany).filter(
                InsuranceCompany.name == ins["name"]
            ).first()
            if existing:
                existing.country = ins["country"]
                existing.region = "EU"
                existing.website = ins["website"]
                print(f"  Updated: {ins['name']}")
            else:
                company = InsuranceCompany(
                    name=ins["name"],
                    country=ins["country"],
                    region="EU",
                    website=ins["website"],
                    is_active=True,
                )
                session.add(company)
                count += 1
                print(f"  Created: {ins['name']}")
        session.commit()
    return count


def seed_eu_car_brands() -> int:
    """Upsert EU car brands. Returns count of new rows."""
    count = 0
    with get_db_session() as session:
        for b in EU_CAR_BRANDS:
            existing = session.query(CarBrand).filter(
                CarBrand.name == b["name"]
            ).first()
            if existing:
                existing.country_of_origin = b["country_of_origin"]
                existing.region = "EU"
                existing.founded_year = b["founded_year"]
                print(f"  Updated: {b['name']}")
            else:
                brand = CarBrand(
                    name=b["name"],
                    country_of_origin=b["country_of_origin"],
                    region="EU",
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
    print("Seeding EU insurance companies")
    print("=" * 56)
    ins_count = seed_eu_insurers()
    print(f"\n  {ins_count} new insurance companies created (region=EU)")

    print()
    print("=" * 56)
    print("Seeding EU car brands")
    print("=" * 56)
    brand_count = seed_eu_car_brands()
    print(f"\n  {brand_count} new car brands created (region=EU)")

    print()
    print("=" * 56)
    print(f"Done — {ins_count + brand_count} total new entities seeded")
    print("=" * 56)


if __name__ == "__main__":
    main()
