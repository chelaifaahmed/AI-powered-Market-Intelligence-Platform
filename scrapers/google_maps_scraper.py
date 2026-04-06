"""
scrapers/google_maps_scraper.py
-------------------------------
Scrapes Google search results to extract Google Maps ratings
and review counts for Tunisian companies.

Stores results in the ``google_maps_signals`` table (created on first run).

Usage:
    python scrapers/google_maps_scraper.py
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
import uuid
from random import uniform

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from database.connection import get_db_session, get_sync_engine
from database.models import InsuranceCompany, CarBrand
from scrapers.user_agents import get_random_user_agent
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("scrapers.google_maps")

# ---------------------------------------------------------------------------
# Target companies and their search queries
# ---------------------------------------------------------------------------
TN_INSURANCE_TARGETS = [
    ("STAR", "star assurances tunisie avis"),
    ("Star Assurances", None),  # skip duplicate
    ("Carte (GAT)", "gat assurances tunisie avis"),
    ("Maghrebia", "maghrebia assurances tunisie avis"),
    ("Lloyd Tunisien", "lloyd tunisien assurances avis"),
    ("BIAT Assurances", "biat assurances tunisie avis"),
    ("Assurances SALIM", "assurances salim tunisie avis"),
    ("Giat Assurances", "giat assurances tunisie avis"),
    ("COMAR Assurances", "comar assurances tunisie avis"),
    ("BH Assurance", "bh assurance tunisie avis"),
    ("ASTREE Assurances", "astree assurances tunisie avis"),
    ("AMI Assurances", "ami assurances tunisie avis"),
]

TN_DEALER_TARGETS = [
    ("Ennakl (Volkswagen/Audi TN)", "ennakl automobiles tunisie avis"),
    ("Artes (Renault TN)", "artes renault tunisie avis"),
    ("STAFIM (Peugeot TN)", "stafim peugeot tunisie avis"),
    ("AutoStar Tunisie", "autostar bmw tunisie avis"),
    ("ATL (Ford TN)", "atl ford tunisie avis"),
    ("SATA (Toyota TN)", "sata toyota tunisie avis"),
    ("Sovac (General Motors TN)", "sovac general motors tunisie avis"),
    ("Tractafric Motors", "tractafric motors tunisie avis"),
]


def _ensure_table(engine) -> None:
    """Create google_maps_signals table if it doesn't exist."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS google_maps_signals (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                company_id UUID NOT NULL,
                company_type VARCHAR(20) NOT NULL,
                company_name VARCHAR(200) NOT NULL,
                google_rating FLOAT,
                google_review_count INTEGER,
                search_query VARCHAR(200),
                raw_snippet TEXT,
                scraped_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.commit()
    logger.info("google_maps_signals table ensured.")


def _scrape_google_rating(query: str) -> dict:
    """
    Search Google for the query and attempt to extract
    a star rating and review count from the result page.
    """
    url = "https://www.google.com/search"
    params = {"q": query, "hl": "fr", "gl": "tn"}
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    result = {
        "rating": None,
        "review_count": None,
        "snippet": None,
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Look for rating patterns in the page text
        page_text = soup.get_text()

        # Pattern: "4.2" or "4,2" followed by possible star indicators
        rating_patterns = [
            r'(\d[.,]\d)\s*/\s*5',           # "4.2/5" or "4,2/5"
            r'(\d[.,]\d)\s*(?:étoile|star)',   # "4.2 étoiles"
            r'Note\s*:\s*(\d[.,]\d)',          # "Note : 4.2"
            r'(\d[.,]\d)\s*\(\d+\s*avis\)',    # "4.2 (123 avis)"
        ]
        for pattern in rating_patterns:
            m = re.search(pattern, page_text, re.IGNORECASE)
            if m:
                rating_str = m.group(1).replace(",", ".")
                rating = float(rating_str)
                if 1.0 <= rating <= 5.0:
                    result["rating"] = rating
                    break

        # Look for review count: "X avis" or "X reviews"
        review_patterns = [
            r'(\d[\d\s.,]*)\s*avis',
            r'(\d[\d\s.,]*)\s*reviews?',
            r'(\d[\d\s.,]*)\s*évaluations?',
            r'(\d[\d\s.,]*)\s*commentaires?',
        ]
        for pattern in review_patterns:
            m = re.search(pattern, page_text, re.IGNORECASE)
            if m:
                count_str = m.group(1).replace(" ", "").replace(".", "").replace(",", "")
                try:
                    count = int(count_str)
                    if count > 0:
                        result["review_count"] = count
                        break
                except ValueError:
                    pass

        # Extract a text snippet from search results
        snippets = soup.select(".VwiC3b, .IsZvec, .s3v9rd")
        if snippets:
            result["snippet"] = snippets[0].get_text()[:500]

    except requests.RequestException as e:
        logger.warning("HTTP error for '%s': %s", query, e)
    except Exception as e:
        logger.warning("Parse error for '%s': %s", query, e)

    return result


def run_google_maps_scraper() -> None:
    """Main entry point: scrape Google for TN company ratings."""
    engine = get_sync_engine()
    _ensure_table(engine)

    results_summary = []

    with get_db_session() as session:
        # Build name→id lookups
        insurers = {c.name: c.id for c in session.query(InsuranceCompany).filter_by(region="TN").all()}
        brands = {b.name: b.id for b in session.query(CarBrand).filter_by(region="TN").all()}

        all_targets = [
            (name, query, "insurance", insurers.get(name))
            for name, query in TN_INSURANCE_TARGETS
        ] + [
            (name, query, "brand", brands.get(name))
            for name, query in TN_DEALER_TARGETS
        ]

        for name, query, company_type, company_id in all_targets:
            if query is None:
                logger.info("SKIP %s (duplicate)", name)
                continue
            if company_id is None:
                logger.warning("SKIP %s — not found in DB", name)
                continue

            logger.info("Scraping: %s → '%s'", name, query)
            data = _scrape_google_rating(query)

            # Upsert into google_maps_signals
            session.execute(text("""
                INSERT INTO google_maps_signals
                    (id, company_id, company_type, company_name,
                     google_rating, google_review_count, search_query, raw_snippet)
                VALUES
                    (:id, :company_id, :company_type, :company_name,
                     :rating, :review_count, :query, :snippet)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": str(uuid.uuid4()),
                "company_id": str(company_id),
                "company_type": company_type,
                "company_name": name,
                "rating": data["rating"],
                "review_count": data["review_count"],
                "query": query,
                "snippet": data["snippet"],
            })

            rating_str = f"{data['rating']}★" if data["rating"] else "N/A"
            count_str = str(data["review_count"]) if data["review_count"] else "0"
            result_line = f"  {name}: {rating_str} ({count_str} reviews)"
            results_summary.append(result_line)
            logger.info(result_line)

            # Rate limiting: 5-10 seconds between requests
            delay = uniform(5, 10)
            logger.info("  Waiting %.1fs ...", delay)
            time.sleep(delay)

        session.commit()

    # Summary
    separator = "=" * 60
    logger.info(separator)
    logger.info("Google Maps Scraper - Results")
    logger.info(separator)
    for line in results_summary:
        logger.info(line)
    logger.info(separator)


if __name__ == "__main__":
    run_google_maps_scraper()
