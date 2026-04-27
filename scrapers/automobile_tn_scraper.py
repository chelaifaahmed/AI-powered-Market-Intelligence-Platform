"""
scrapers/automobile_tn_scraper.py
-----------------------------------
Scraper for automobile.tn — new car prices in Tunisia (DT / TND).

Each brand page at https://www.automobile.tn/fr/neuf/{brand} lists all
available models with their starting price in Tunisian Dinar and EUR.

Target model: CarListing  (condition='new', currency='TND', country='TN')
Data origin:  scraped
Region:       TN

Public API:
    run_automobile_tn_scraper() -> dict  (metrics)
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

logger = logging.getLogger("scrapers.automobile_tn")

_BASE_URL = "https://www.automobile.tn"
_SOURCE_NAME = "Automobile.Tn"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Brands present on automobile.tn that map cleanly to CarBrand names in our DB.
# key = automobile.tn URL slug, value = substring to match in CarBrand.name (case-insensitive)
_BRAND_SLUGS: List[Tuple[str, str]] = [
    ("toyota",        "toyota"),
    ("volkswagen",    "volkswagen"),
    ("bmw",           "bmw"),
    ("mercedes-benz", "mercedes"),
    ("renault",       "renault"),
    ("peugeot",       "peugeot"),
    ("hyundai",       "hyundai"),
    ("kia",           "kia"),
    ("ford",          "ford"),
    ("honda",         "honda"),
    ("nissan",        "nissan"),
    ("fiat",          "fiat"),
    ("audi",          "audi"),
    ("citroen",       "citroen"),
    ("chevrolet",     "chevrolet"),
    ("jeep",          "jeep"),
    ("seat",          "seat"),
    ("skoda",         "skoda"),
    ("mg",            "mg"),
    ("mitsubishi",    "mitsubishi"),
    ("suzuki",        "suzuki"),
    ("dacia",         "dacia"),
    ("opel",          "opel"),
    ("land-rover",    "land rover"),
    ("volvo",         "volvo"),
    ("mini",          "mini"),
    ("porsche",       "porsche"),
    ("byd",           "byd"),
    ("geely",         "geely"),
    ("chery",         "chery"),
]

# Price pattern: "à partir de 84 900 DT" or "119.800 DT"
_PRICE_DT_RE = re.compile(r"(?:partir de\s+)?([\d\s.]+)\s*DT", re.I)
# EUR price: "19 000 € HT" or "24 000 €"
_PRICE_EUR_RE = re.compile(r"([\d\s.]+)\s*€", re.I)


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

def _fetch_html(url: str, timeout: int = 15) -> Optional[str]:
    req = Request(url, headers={
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return raw.decode("utf-8", errors="replace")
    except HTTPError as e:
        logger.warning("HTTP %s fetching %s", e.code, url)
    except URLError as e:
        logger.warning("URLError fetching %s: %s", url, e.reason)
    except Exception as e:
        logger.warning("Error fetching %s: %s", url, e)
    return None


# ---------------------------------------------------------------------------
# Price parsing
# ---------------------------------------------------------------------------

def _parse_price_dt(text: str) -> Optional[float]:
    """Extract Tunisian Dinar price from text like 'à partir de 84 900 DT'."""
    m = _PRICE_DT_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(" ", "").replace(".", "").replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _clean_model_name(raw: str, brand_slug: str) -> str:
    """Strip brand name prefix and clean up model name from link text."""
    # Remove known brand prefixes (e.g. "Toyota " from "Toyota Yaris Hybride")
    brand_clean = brand_slug.replace("-", " ").title()
    name = raw
    if name.lower().startswith(brand_clean.lower()):
        name = name[len(brand_clean):].strip()
    # Strip price info that bleeds into the text
    for pattern in [r"à partir de.*", r"\d[\d\s.]*DT.*", r"\d[\d\s.]*€.*"]:
        name = re.sub(pattern, "", name, flags=re.I).strip()
    return name[:200] or raw[:200]


# ---------------------------------------------------------------------------
# Brand page parser
# ---------------------------------------------------------------------------

def _parse_brand_page(html: str, brand_slug: str) -> List[Dict]:
    """Extract model listings from an automobile.tn brand page."""
    soup = BeautifulSoup(html, "html.parser")
    models = []
    seen_urls = set()

    for a in soup.find_all("a", href=re.compile(rf"^/fr/neuf/{brand_slug}/")):
        href = a["href"]
        if href in seen_urls:
            continue
        # Skip non-model links (e.g. /fr/neuf/toyota/devis, /fr/neuf/toyota/concessionnaires)
        parts = href.strip("/").split("/")
        if len(parts) < 4:
            continue
        if parts[3] in ("devis", "concessionnaires", "comparateur", "occasions", "avis"):
            continue

        full_url = _BASE_URL + href
        text = a.get_text(" ", strip=True)

        price_dt = _parse_price_dt(text)
        if price_dt is None or price_dt <= 0:
            continue  # skip links without a valid price

        model_name = _clean_model_name(text, brand_slug)
        if not model_name:
            continue

        seen_urls.add(href)
        models.append({
            "model_name": model_name,
            "listing_url": full_url,
            "listed_price": price_dt,
            "currency": "TND",
            "country": "TN",
            "condition": "new",
        })
        logger.debug("  Found: %s — %.0f TND", model_name, price_dt)

    return models


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_or_create_brand(session, brand_slug: str, brand_match: str):
    """Return CarBrand matching brand_match substring, or create TN entry."""
    from database.models import CarBrand

    brands = session.query(CarBrand).filter(CarBrand.is_active.is_(True)).all()
    for b in brands:
        if brand_match.lower() in b.name.lower():
            return b

    # Not found — create a minimal TN brand record
    brand_name = brand_slug.replace("-", " ").title() + " (TN)"
    existing = session.query(CarBrand).filter(CarBrand.name == brand_name).first()
    if existing:
        return existing

    new_brand = CarBrand(
        name=brand_name,
        country_of_origin="TN",
        region="TN",
        is_active=True,
    )
    session.add(new_brand)
    session.flush()
    logger.info("Created new CarBrand: %s", brand_name)
    return new_brand


def _get_or_create_model(session, brand, model_name: str):
    """Return CarModel for brand+name, or create it."""
    from database.models import CarModel

    existing = (
        session.query(CarModel)
        .filter(CarModel.brand_id == brand.id, CarModel.name == model_name)
        .first()
    )
    if existing:
        return existing

    new_model = CarModel(
        brand_id=brand.id,
        name=model_name,
        segment="unknown",
    )
    session.add(new_model)
    session.flush()
    logger.info("Created CarModel: %s / %s", brand.name, model_name)
    return new_model


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_automobile_tn_scraper(
    brand_slugs: Optional[List[Tuple[str, str]]] = None,
    rate_limit_s: float = 1.5,
) -> Dict:
    """Scrape automobile.tn for new-car prices and store as CarListing records.

    Args:
        brand_slugs: list of (url_slug, db_match_str) tuples. Defaults to _BRAND_SLUGS.
        rate_limit_s: seconds to wait between brand page fetches.

    Returns:
        metrics dict: {brands_scraped, models_found, inserted, duplicate, errors}
    """
    import os, sys
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    from database.connection import get_db_session
    from database.enums import ListingCondition
    from database.models import CarListing, ReviewSource

    if brand_slugs is None:
        brand_slugs = _BRAND_SLUGS

    metrics = {
        "brands_scraped": 0,
        "models_found": 0,
        "inserted": 0,
        "duplicate": 0,
        "errors": 0,
    }

    with get_db_session() as session:
        # Resolve source record
        source = session.query(ReviewSource).filter_by(name=_SOURCE_NAME).first()
        if not source:
            from database.enums import SourceType
            source = ReviewSource(
                name=_SOURCE_NAME,
                base_url=_BASE_URL + "/fr/neuf",
                reliability_score=0.90,
                is_active=True,
                region="TN",
                source_type=SourceType.PRICING_PAGE,
            )
            session.add(source)
            session.flush()

        for i, (slug, match_str) in enumerate(brand_slugs):
            brand_url = f"{_BASE_URL}/fr/neuf/{slug}"
            logger.info("[%d/%d] Scraping %s", i + 1, len(brand_slugs), brand_url)

            html = _fetch_html(brand_url)
            if not html:
                metrics["errors"] += 1
                continue

            listings = _parse_brand_page(html, slug)
            metrics["brands_scraped"] += 1
            metrics["models_found"] += len(listings)

            if not listings:
                logger.info("  No priced models found for %s", slug)
                time.sleep(rate_limit_s)
                continue

            # Resolve brand once per brand page
            brand = _get_or_create_brand(session, slug, match_str)

            for item in listings:
                listing_url = item["listing_url"]
                content_hash = hashlib.sha256(listing_url.encode()).hexdigest()

                # Deduplicate by URL
                exists = session.query(CarListing).filter(
                    CarListing.listing_url == listing_url
                ).first()
                if exists:
                    metrics["duplicate"] += 1
                    continue

                try:
                    model = _get_or_create_model(session, brand, item["model_name"])
                    listing = CarListing(
                        model_id=model.id,
                        source_id=source.id,
                        listing_url=listing_url,
                        listed_price=item["listed_price"],
                        currency=item["currency"],
                        country=item["country"],
                        condition=ListingCondition.NEW,
                        city="Tunisia",
                        scraped_at=datetime.now(timezone.utc),
                        data_origin="scraped",
                        is_active=True,
                    )
                    session.add(listing)
                    session.flush()
                    metrics["inserted"] += 1
                    logger.info(
                        "  Inserted: %s / %s — %.0f TND",
                        brand.name, item["model_name"], item["listed_price"]
                    )
                except Exception as e:
                    session.rollback()
                    metrics["errors"] += 1
                    logger.warning(
                        "  Failed inserting %s: %s", item["model_name"], e
                    )

            # Polite rate limit
            if i < len(brand_slugs) - 1:
                time.sleep(rate_limit_s)

        # Update source metadata
        source.total_records_scraped = (source.total_records_scraped or 0) + metrics["inserted"]
        source.last_scraped_at = datetime.now(timezone.utc)
        session.flush()

    logger.info("Automobile.tn scrape complete: %s", metrics)
    return metrics
