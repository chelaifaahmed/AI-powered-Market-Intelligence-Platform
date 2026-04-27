"""
scrapers/nhtsa_complaints_scraper.py
--------------------------------------
Fetches real consumer complaint data from the US NHTSA (National Highway
Traffic Safety Administration) public API — no API key required.

Complaints are stored as CarReview rows (review_text = complaint summary,
rating = null since NHTSA has no star rating system).

API docs: https://api.nhtsa.gov/  (public, free, unlimited)

Public API:
    run_nhtsa_complaints_scraper(years_back=3) -> dict
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger("scrapers.nhtsa_complaints")

_BASE_URL = "https://api.nhtsa.gov/complaints/complaintsByVehicle"
_USER_AGENT = "TW-Intel/1.0 (PFE Market Intelligence Platform)"

# NHTSA make names must match exactly (case-insensitive in API but uppercase is safer)
# Maps our DB brand names → NHTSA make names
_BRAND_TO_NHTSA: Dict[str, str] = {
    "Toyota":     "TOYOTA",
    "Volkswagen": "VOLKSWAGEN",
    "Peugeot":    "PEUGEOT",
    "Renault":    "RENAULT",
    "Hyundai":    "HYUNDAI",
    "Kia":        "KIA",
    "BMW":        "BMW",
    "Mercedes":   "MERCEDES-BENZ",
    "Ford":       "FORD",
    "Honda":      "HONDA",
    "Nissan":     "NISSAN",
    "Audi":       "AUDI",
    "Citroën":    "CITROEN",
    "Citroën":    "CITROEN",
    "Citroen":    "CITROEN",
    "Opel":       "OPEL",
    "Fiat":       "FIAT",
    "Jeep":       "JEEP",
    "Dodge":      "DODGE",
    "Chevrolet":  "CHEVROLET",
    "Tesla":      "TESLA",
    "Volvo":      "VOLVO",
    "Mazda":      "MAZDA",
    "Subaru":     "SUBARU",
    "Mitsubishi": "MITSUBISHI",
    "Suzuki":     "SUZUKI",
    "Seat":       "SEAT",
    "Skoda":      "SKODA",
    "Dacia":      "DACIA",
}


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _fetch_complaints(make: str, model: str, year: int, timeout: int = 15) -> List[Dict]:
    """Fetch NHTSA complaints for a specific make/model/year. Returns list of complaint dicts."""
    params = urlencode({"make": make, "model": model, "modelYear": year})
    url = f"{_BASE_URL}?{params}"
    req = Request(url, headers={
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            return data.get("results", [])
    except HTTPError as e:
        if e.code != 404:
            logger.warning("HTTP %s fetching NHTSA %s %s %d", e.code, make, model, year)
    except URLError as e:
        logger.warning("URLError fetching NHTSA %s %s %d: %s", make, model, year, e.reason)
    except Exception as e:
        logger.warning("Error fetching NHTSA %s %s %d: %s", make, model, year, e)
    return []


def _fetch_models_for_make(make: str, timeout: int = 15) -> List[str]:
    """Ask NHTSA for all model names under a given make."""
    url = f"https://api.nhtsa.gov/vehicles/getModelsForMake/{make}?format=json"
    req = Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            return [r["Model_Name"].upper() for r in data.get("Results", [])]
    except Exception as e:
        logger.warning("Error fetching NHTSA models for %s: %s", make, e)
    return []


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_or_create_source(session):
    from database.models import ReviewSource
    from database.enums import SourceType

    source = session.query(ReviewSource).filter_by(name="NHTSA Complaints").first()
    if source:
        return source
    source = ReviewSource(
        name="NHTSA Complaints",
        base_url="https://api.nhtsa.gov",
        reliability_score=0.95,
        is_active=True,
        region="US",
        source_type=SourceType.AUTOMOTIVE_REVIEW,
    )
    session.add(source)
    session.flush()
    logger.info("Created ReviewSource: NHTSA Complaints")
    return source


def _insert_complaint(session, complaint: Dict, model_id, source_id) -> bool:
    """Insert one NHTSA complaint as a CarReview. Returns True if inserted."""
    from database.models import CarReview

    summary = (complaint.get("summary") or "").strip()
    if not summary or len(summary) < 10:
        return False

    odi = str(complaint.get("odiNumber") or "")
    content_hash = hashlib.sha256(f"nhtsa|{model_id}|{odi}".encode()).hexdigest()

    exists = session.query(CarReview).filter_by(content_hash=content_hash).first()
    if exists:
        return False

    # Parse complaint date (format: "YYYYMMDD" as integer or string)
    review_date = None
    raw_date = complaint.get("dateComplaintFiled") or complaint.get("dateOfIncident")
    if raw_date:
        try:
            ds = str(raw_date)
            if len(ds) == 8 and ds.isdigit():
                review_date = datetime(int(ds[:4]), int(ds[4:6]), int(ds[6:8])).date()
        except Exception:
            pass

    # Build a rich review text
    components = complaint.get("components") or ""
    crash = complaint.get("crash", False)
    fire = complaint.get("fire", False)
    injuries = int(complaint.get("numberOfInjuries") or 0)
    deaths = int(complaint.get("numberOfDeaths") or 0)

    flags = []
    if crash:
        flags.append("CRASH")
    if fire:
        flags.append("FIRE")
    if injuries:
        flags.append(f"{injuries} INJURIES")
    if deaths:
        flags.append(f"{deaths} DEATHS")
    flag_str = f"[{', '.join(flags)}] " if flags else ""

    comp_str = f"Components: {components}. " if components else ""
    review_text = f"{flag_str}{comp_str}{summary}"[:2000]

    source_url = (
        f"https://www.nhtsa.gov/vehicle-safety/complaints#id={odi}"
        if odi else "https://api.nhtsa.gov/complaints/complaintsByVehicle"
    )

    from parsers.data_gateway import clean_car_review
    cleaned = clean_car_review({
        "review_text": review_text,
        "review_title": f"NHTSA Complaint #{odi}" if odi else "NHTSA Complaint",
        "source_url": source_url,
        "rating": None,
        "author": None,
        "review_date": review_date,
    })
    if cleaned is None:
        return False

    record = CarReview(
        model_id=model_id,
        source_id=source_id,
        source_url=cleaned["source_url"],
        rating=cleaned["rating"],
        review_title=cleaned["review_title"],
        review_text=cleaned["review_text"],
        author=cleaned["author"],
        review_date=cleaned["review_date"],
        is_verified=True,
        content_hash=content_hash,
        data_origin="scraped",
        is_processed=False,
    )
    session.add(record)
    try:
        session.flush()
        return True
    except Exception as e:
        session.rollback()
        logger.warning("Insert failed for NHTSA complaint: %s", e)
        return False


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_nhtsa_complaints_scraper(years_back: int = 3) -> Dict:
    """
    Fetch NHTSA consumer complaints for all car brands/models in the DB.

    Args:
        years_back: How many recent model years to query (default 3 → 2022-2024)

    Returns:
        metrics dict: {fetched, inserted, duplicate, skipped, errors, by_brand}
    """
    import os, sys
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    from database.connection import get_db_session
    from database.models import CarBrand, CarModel

    current_year = datetime.now().year
    target_years = list(range(current_year - years_back + 1, current_year + 1))

    metrics: Dict = {
        "fetched": 0,
        "inserted": 0,
        "duplicate": 0,
        "skipped": 0,
        "errors": 0,
        "by_brand": {},
    }

    with get_db_session() as session:
        source = _get_or_create_source(session)
        brands = session.query(CarBrand).filter_by(is_active=True).all()

        for brand in brands:
            nhtsa_make = _BRAND_TO_NHTSA.get(brand.name)
            if not nhtsa_make:
                # Try case-insensitive lookup
                nhtsa_make = next(
                    (v for k, v in _BRAND_TO_NHTSA.items() if k.lower() == brand.name.lower()),
                    None,
                )
            if not nhtsa_make:
                logger.info("No NHTSA mapping for brand %r — skipping", brand.name)
                metrics["skipped"] += 1
                continue

            brand_metrics = {"inserted": 0, "duplicate": 0, "errors": 0, "fetched": 0}
            models = session.query(CarModel).filter_by(brand_id=brand.id).all()

            if not models:
                logger.info("[%s] No models in DB — skipping", brand.name)
                metrics["skipped"] += 1
                continue

            logger.info("[%s] Scraping NHTSA complaints for %d models × %d years",
                        brand.name, len(models), len(target_years))

            for model in models:
                for year in target_years:
                    # NHTSA model names must be uppercase and match exactly
                    nhtsa_model = model.name.upper()
                    complaints = _fetch_complaints(nhtsa_make, nhtsa_model, year)

                    if complaints:
                        logger.info("[%s] %s %d -> %d complaints",
                                    brand.name, model.name, year, len(complaints))

                    brand_metrics["fetched"] += len(complaints)
                    metrics["fetched"] += len(complaints)

                    for complaint in complaints:
                        if _insert_complaint(session, complaint, model.id, source.id):
                            brand_metrics["inserted"] += 1
                            metrics["inserted"] += 1
                        else:
                            brand_metrics["duplicate"] += 1
                            metrics["duplicate"] += 1

                    time.sleep(0.3)  # gentle pacing

            metrics["by_brand"][brand.name] = brand_metrics
            logger.info("[%s] Done: %s", brand.name, brand_metrics)

            source.total_records_scraped = (source.total_records_scraped or 0) + brand_metrics["inserted"]
            source.last_scraped_at = datetime.now(timezone.utc)
            session.flush()

            time.sleep(0.5)  # pause between brands

    logger.info(
        "NHTSA scrape complete: fetched=%d inserted=%d duplicate=%d skipped=%d",
        metrics["fetched"], metrics["inserted"], metrics["duplicate"], metrics["skipped"],
    )
    return metrics
