#!/usr/bin/env python3
"""
scripts/seed_tunisia_data.py
-------------------------------
Seeds Tunisian insurance companies into the database.

These represent the major insurers operating in the Tunisian market,
relevant for TEAMWILL's ERP and leasing system clients.

Usage:
    python scripts/seed_tunisia_data.py
"""

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from database.connection import get_db_session
from database.models import InsuranceCompany

# ---------------------------------------------------------------------------
# Tunisian insurance companies
# ---------------------------------------------------------------------------
TUNISIAN_INSURERS = [
    {"name": "Maghrebia",           "country": "Tunisia", "website": "https://www.maghrebia.com.tn"},
    {"name": "BIAT Assurances",     "country": "Tunisia", "website": "https://www.biatassurances.com.tn"},
    {"name": "Giat Assurances",     "country": "Tunisia", "website": "https://www.gat.com.tn"},
    {"name": "Star Assurances",     "country": "Tunisia", "website": "https://www.star.com.tn"},
    {"name": "Carte (GAT)",         "country": "Tunisia", "website": "https://www.carte.com.tn"},
    {"name": "STAR",                "country": "Tunisia", "website": "https://www.star.com.tn"},
    {"name": "Assurances SALIM",    "country": "Tunisia", "website": "https://www.salim.com.tn"},
    {"name": "Lloyd Tunisien",      "country": "Tunisia", "website": "https://www.lloydtunisien.com.tn"},
]


def seed_tunisian_insurers() -> int:
    """Upsert Tunisian insurance companies. Returns count of new rows."""
    count = 0
    with get_db_session() as session:
        for ins in TUNISIAN_INSURERS:
            existing = session.query(InsuranceCompany).filter(
                InsuranceCompany.name == ins["name"]
            ).first()
            if existing:
                existing.country = ins["country"]
                existing.region = "TN"
                existing.website = ins["website"]
                print(f"  Updated: {ins['name']}")
            else:
                company = InsuranceCompany(
                    name=ins["name"],
                    country=ins["country"],
                    region="TN",
                    website=ins["website"],
                    is_active=True,
                )
                session.add(company)
                count += 1
                print(f"  Created: {ins['name']}")
        session.commit()
    return count


def main():
    print("=" * 56)
    print("Seeding Tunisian insurance companies")
    print("=" * 56)
    created = seed_tunisian_insurers()
    print(f"\nDone — {created} new companies created (region=TN)")
    print("=" * 56)


if __name__ == "__main__":
    main()
