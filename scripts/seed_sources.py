"""
scripts/seed_sources.py
-----------------------
Seeds the review_sources table with the existing scrapers in the codebase.
Skips any source whose name already exists (idempotent).

Usage:
    python -m scripts.seed_sources
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db_session
from database.models import ReviewSource
from database.enums import SourceType

SOURCES = [
    {
        "name": "Trustpilot",
        "base_url": "https://www.trustpilot.com",
        "source_type": SourceType.AUTOMOTIVE_REVIEW,
        "region": "EU",
        "keywords": ["car", "automobile", "vehicle", "dealer"],
        "reliability_score": 0.85,
    },
    {
        "name": "AutoScout24",
        "base_url": "https://www.autoscout24.com",
        "source_type": SourceType.MARKETPLACE,
        "region": "EU",
        "keywords": ["car listing", "used car", "dealer"],
        "reliability_score": 0.90,
    },
    {
        "name": "Car and Driver",
        "base_url": "https://www.caranddriver.com",
        "source_type": SourceType.AUTOMOTIVE_REVIEW,
        "region": "US",
        "keywords": ["car review", "test drive", "automotive"],
        "reliability_score": 0.90,
    },
    {
        "name": "Edmunds",
        "base_url": "https://www.edmunds.com",
        "source_type": SourceType.AUTOMOTIVE_REVIEW,
        "region": "US",
        "keywords": ["car review", "pricing", "dealer"],
        "reliability_score": 0.88,
    },
    {
        "name": "Reuters Automotive",
        "base_url": "https://www.reuters.com",
        "source_type": SourceType.NEWS_BLOG,
        "region": "Global",
        "keywords": ["automotive", "EV", "industry news"],
        "reliability_score": 0.95,
    },
    {
        "name": "Insurance Review Aggregator",
        "base_url": "https://www.insurancereviews.example.com",
        "source_type": SourceType.INSURANCE_REVIEW,
        "region": "EU",
        "keywords": ["insurance", "auto insurance", "claims"],
        "reliability_score": 0.75,
    },
    {
        "name": "Competitor Pricing Feed",
        "base_url": "https://pricing.example.com",
        "source_type": SourceType.PRICING_PAGE,
        "region": "TN",
        "keywords": ["insurance pricing", "premium", "competitor"],
        "reliability_score": 0.80,
    },
    {
        "name": "RSS Market News",
        "base_url": "https://feeds.example.com/automotive",
        "source_type": SourceType.TREND_ARTICLE,
        "region": "Global",
        "keywords": ["market trend", "EV", "regulation"],
        "reliability_score": 0.82,
    },
    {
        "name": "Forum Scraper",
        "base_url": "https://forums.example.com",
        "source_type": SourceType.FORUM,
        "region": "TN",
        "keywords": ["Tunisia", "car forum", "user opinion"],
        "reliability_score": 0.65,
    },
]


def main():
    with get_db_session() as session:
        created = 0
        skipped = 0
        for src_data in SOURCES:
            exists = session.query(ReviewSource).filter(ReviewSource.name == src_data["name"]).first()
            if exists:
                skipped += 1
                print(f"  SKIP  {src_data['name']} (already exists)")
                continue

            src = ReviewSource(**src_data)
            session.add(src)
            created += 1
            print(f"  ADD   {src_data['name']}")

        session.flush()
        print(f"\nDone: {created} created, {skipped} skipped.")


if __name__ == "__main__":
    main()
