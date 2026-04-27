"""
scrapers/google_places_scraper.py
-----------------------------------
Fetch real customer reviews for Tunisian insurance companies and car dealers
from the Google Places API (Text Search + Place Details).

SETUP REQUIRED (one-time):
  1. Go to https://console.cloud.google.com/
  2. Enable: "Places API" (not "Places API (New)")
  3. Create an API key → restrict it to "Places API"
  4. Add to your .env:
       GOOGLE_PLACES_API_KEY=AIza...

Data written to:
  - InsuranceReview  (for insurance companies)
  - CarReview        (for car dealers / brands)

Both marked data_origin='scraped'.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

logger = logging.getLogger("scrapers.google_places")

_PLACES_API_BASE = "https://maps.googleapis.com/maps/api/place"
_USER_AGENT = "TW-Intel/1.0"

# Tunisian insurance companies to search for
_TN_INSURANCE_COMPANIES = [
    "Star Assurances Tunis",
    "GAT Assurances Tunis",
    "STAR Assurances",
    "Maghrebia Assurances",
    "Carte Assurances Tunis",
    "AMI Assurances Tunis",
    "ASTREE Assurances",
    "BH Assurance Tunis",
    "COMAR Assurances Tunis",
    "Tunis Re",
    "CTAMA Assurances",
    "SALIM Assurances",
]

# Tunisian car dealerships / brand references
_TN_CAR_DEALERS = [
    "ENNAKL automobiles Tunis",
    "SATA Toyota Tunis",
    "ARTES Volkswagen Tunis",
    "STAFIM Peugeot Tunis",
    "Renault Tunis",
    "Hyundai Tunisia",
    "Kia Motors Tunis",
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(url: str, timeout: int = 15) -> Optional[Dict]:
    req = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning("HTTP error: %s  url=%s", e, url[:100])
        return None


def _search_place(query: str, api_key: str) -> Optional[str]:
    """Return the first place_id matching the query string."""
    params = urlencode({"query": query, "key": api_key, "language": "fr", "region": "TN"})
    url = f"{_PLACES_API_BASE}/textsearch/json?{params}"
    data = _get(url)
    if not data or data.get("status") != "OK":
        logger.warning("Text search failed for %r: %s", query, data.get("status") if data else "no response")
        return None
    results = data.get("results", [])
    if not results:
        return None
    place_id = results[0]["place_id"]
    logger.info("Found place_id=%s for %r", place_id, query)
    return place_id


def _get_place_reviews(place_id: str, api_key: str) -> Optional[Dict]:
    """Fetch place details including reviews (max 5 per place, Google limit)."""
    params = urlencode({
        "place_id": place_id,
        "fields": "name,rating,user_ratings_total,reviews",
        "key": api_key,
        "language": "fr",
    })
    url = f"{_PLACES_API_BASE}/details/json?{params}"
    data = _get(url)
    if not data or data.get("status") != "OK":
        logger.warning("Place details failed for %s: %s", place_id, data.get("status") if data else "no response")
        return None
    return data.get("result")


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _store_insurance_reviews(session, company_name: str, place_result: Dict, source_id) -> int:
    """Match or create InsuranceCompany, store Google reviews."""
    from database.models import InsuranceCompany, InsuranceReview
    from sqlalchemy import func

    reviews = place_result.get("reviews", [])
    if not reviews:
        return 0

    # Fuzzy-match company
    company = (
        session.query(InsuranceCompany)
        .filter(func.lower(InsuranceCompany.name).contains(company_name.split()[0].lower()))
        .first()
    )
    if not company:
        # Create a minimal record so reviews have a home
        company = InsuranceCompany(
            name=company_name,
            country="TN",
            region="TN",
            data_origin="scraped",
        )
        session.add(company)
        session.flush()
        logger.info("Created InsuranceCompany: %s", company_name)

    inserted = 0
    for rev in reviews:
        text = (rev.get("text") or "").strip()
        if not text:
            continue
        rating = rev.get("rating")
        author = rev.get("author_name", "")
        # Google uses epoch seconds for time
        epoch = rev.get("time")
        pub_date = datetime.fromtimestamp(epoch, tz=timezone.utc).date() if epoch else None

        content_hash = hashlib.sha256(f"google|{company.id}|{author}|{text[:100]}".encode()).hexdigest()
        exists = session.query(InsuranceReview).filter_by(content_hash=content_hash).first()
        if exists:
            continue

        record = InsuranceReview(
            company_id=company.id,
            source_id=source_id,
            rating=float(rating) if rating is not None else None,
            review_text=text[:2000],
            reviewer_name=author,
            review_date=pub_date,
            source_url=f"https://maps.google.com/?cid={place_result.get('place_id', '')}",
            content_hash=content_hash,
            data_origin="scraped",
            language="fr",
        )
        session.add(record)
        try:
            session.flush()
            inserted += 1
        except Exception as e:
            session.rollback()
            logger.warning("Insert failed for review: %s", e)

    return inserted


def _store_car_reviews(session, dealer_name: str, place_result: Dict, source_id) -> int:
    """Try to link to a CarBrand via the dealer name; store reviews as CarReview."""
    from database.models import CarBrand, CarModel, CarReview
    from sqlalchemy import func

    reviews = place_result.get("reviews", [])
    if not reviews:
        return 0

    # Attempt brand match (e.g. "ENNAKL Volkswagen" → Volkswagen)
    brand = None
    for word in dealer_name.split():
        if len(word) > 3:
            brand = session.query(CarBrand).filter(
                func.lower(CarBrand.name).contains(word.lower())
            ).first()
            if brand:
                break

    if not brand:
        logger.info("No CarBrand match for dealer %r — skipping", dealer_name)
        return 0

    # Get or create a generic model to attach reviews
    model = session.query(CarModel).filter_by(brand_id=brand.id).first()
    if not model:
        logger.info("No CarModel found for brand %s — skipping", brand.name)
        return 0

    inserted = 0
    for rev in reviews:
        text = (rev.get("text") or "").strip()
        if not text:
            continue
        rating = rev.get("rating")
        author = rev.get("author_name", "")
        epoch = rev.get("time")
        pub_date = datetime.fromtimestamp(epoch, tz=timezone.utc).date() if epoch else None

        content_hash = hashlib.sha256(f"google|{brand.id}|{author}|{text[:100]}".encode()).hexdigest()
        exists = session.query(CarReview).filter_by(content_hash=content_hash).first()
        if exists:
            continue

        record = CarReview(
            model_id=model.id,
            source_id=source_id,
            rating=float(rating) if rating is not None else None,
            review_text=text[:2000],
            reviewer_name=author,
            review_date=pub_date,
            source_url=f"https://maps.google.com/",
            content_hash=content_hash,
            data_origin="scraped",
            language="fr",
        )
        session.add(record)
        try:
            session.flush()
            inserted += 1
        except Exception as e:
            session.rollback()
            logger.warning("Insert failed for car review: %s", e)

    return inserted


# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------

def run_google_places_scraper(
    include_insurance: bool = True,
    include_cars: bool = True,
) -> Dict:
    """
    Scrape Google Places reviews for TN companies.

    Requires GOOGLE_PLACES_API_KEY in environment.
    Returns metrics dict.
    """
    import sys
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key:
        logger.error(
            "GOOGLE_PLACES_API_KEY not set. "
            "Add it to .env to activate this scraper. "
            "See scrapers/google_places_scraper.py for setup instructions."
        )
        return {"error": "GOOGLE_PLACES_API_KEY not configured", "inserted": 0}

    from database.connection import get_db_session
    from database.models import ReviewSource
    from database.enums import SourceType

    metrics = {"fetched": 0, "inserted_insurance": 0, "inserted_car": 0, "errors": 0, "not_found": 0}

    with get_db_session() as session:
        source = session.query(ReviewSource).filter_by(name="Google Places").first()
        if not source:
            source = ReviewSource(
                name="Google Places",
                base_url="https://maps.google.com",
                reliability_score=0.90,
                is_active=True,
                region="TN",
                source_type=SourceType.REVIEW_PLATFORM,
            )
            session.add(source)
            session.flush()

        if include_insurance:
            for company in _TN_INSURANCE_COMPANIES:
                logger.info("Searching Google Places: %r", company)
                place_id = _search_place(company, api_key)
                if not place_id:
                    metrics["not_found"] += 1
                    time.sleep(0.5)
                    continue
                result = _get_place_reviews(place_id, api_key)
                if not result:
                    metrics["errors"] += 1
                    time.sleep(0.5)
                    continue
                metrics["fetched"] += len(result.get("reviews", []))
                n = _store_insurance_reviews(session, company, result, source.id)
                metrics["inserted_insurance"] += n
                logger.info("  → inserted %d reviews for %s", n, company)
                time.sleep(1.0)  # respect rate limit

        if include_cars:
            for dealer in _TN_CAR_DEALERS:
                logger.info("Searching Google Places: %r", dealer)
                place_id = _search_place(dealer, api_key)
                if not place_id:
                    metrics["not_found"] += 1
                    time.sleep(0.5)
                    continue
                result = _get_place_reviews(place_id, api_key)
                if not result:
                    metrics["errors"] += 1
                    time.sleep(0.5)
                    continue
                metrics["fetched"] += len(result.get("reviews", []))
                n = _store_car_reviews(session, dealer, result, source.id)
                metrics["inserted_car"] += n
                logger.info("  → inserted %d reviews for %s", n, dealer)
                time.sleep(1.0)

        total_inserted = metrics["inserted_insurance"] + metrics["inserted_car"]
        source.total_records_scraped = (source.total_records_scraped or 0) + total_inserted
        source.last_scraped_at = datetime.now(timezone.utc)
        session.flush()

    logger.info("Google Places scrape done: %s", metrics)
    return metrics
