"""
scripts/run_listings_ingest.py
-------------------------------
Real car listing ingestion using Playwright to render AutoScout24 search pages.

Full end-to-end path:
    Playwright fetch with networkidle wait
    → full JS-rendered HTML stored in raw_pages
    → JSON-LD + structured HTML extraction of individual listings
    → CarListing rows inserted with data_origin='scraped'

AutoScout24 embeds structured JSON-LD (schema.org/ItemList / schema.org/Offer)
after JavaScript execution.  This script waits for the listing grid to appear
before capturing content.

Usage:
    python scripts/run_listings_ingest.py
    python scripts/run_listings_ingest.py --pages 3 --max-per-page 20
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("scripts.listings_ingest")

# ---------------------------------------------------------------------------
# AutoScout24 search URLs — used car listings, European cities, common brands
# Each URL targets a different brand/location to get diversity
# ---------------------------------------------------------------------------
SEARCH_URLS = [
    # Toyota listings in Germany
    "https://www.autoscout24.com/lst/toyota?sort=standard&desc=0&offer=U&ustate=N%2CU&size=20&cy=D",
    # Volkswagen listings in Germany
    "https://www.autoscout24.com/lst/volkswagen?sort=standard&desc=0&offer=U&ustate=N%2CU&size=20&cy=D",
    # BMW listings in Germany
    "https://www.autoscout24.com/lst/bmw?sort=standard&desc=0&offer=U&ustate=N%2CU&size=20&cy=D",
    # Electric vehicles
    "https://www.autoscout24.com/lst?sort=standard&desc=0&offer=U&ustate=N%2CU&size=20&fuel=E&cy=D",
]

_SOURCE_NAME = "AutoScout24"
_SOURCE_BASE = "https://www.autoscout24.com"
_RELIABILITY_SCORE = 0.90


# ---------------------------------------------------------------------------
# Playwright fetch with JS rendering
# ---------------------------------------------------------------------------

def _fetch_rendered_html(url: str, wait_timeout_ms: int = 15000) -> Optional[str]:
    """
    Launch Playwright, navigate to url, wait for listing cards to appear,
    then return the fully rendered HTML.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.error("playwright is not installed. Run: pip install playwright && playwright install chromium")
        return None

    html: Optional[str] = None
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()
        try:
            resp = page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            http_status = resp.status if resp else None
            logger.info("Navigated to %s — HTTP %s", url, http_status)

            # Wait for listing grid or article cards to appear
            try:
                page.wait_for_selector(
                    "article[data-testid='regular-ad'], .cldt-summary-full-item, [class*='ListItem'], article",
                    timeout=wait_timeout_ms,
                )
                logger.info("Listing cards detected — capturing HTML")
            except PWTimeout:
                logger.info("Selector timeout — capturing whatever is rendered")

            # Scroll to trigger lazy-loading
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            page.wait_for_timeout(1500)

            html = page.content()
            logger.info("Captured %d chars of rendered HTML", len(html))

        except PWTimeout:
            logger.warning("Page load timeout for %s", url)
        except Exception as e:
            logger.error("Error fetching %s: %s", url, e)
        finally:
            page.close()
            context.close()
            browser.close()

    return html


# ---------------------------------------------------------------------------
# Listing extraction from rendered HTML
# ---------------------------------------------------------------------------

def _extract_json_ld(html: str) -> List[Dict]:
    """Extract all JSON-LD objects from rendered HTML."""
    results = []
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(match.group(1).strip())
            results.append(data)
        except json.JSONDecodeError:
            pass
    return results


def _extract_window_state(html: str) -> Optional[Dict]:
    """Try to extract __INITIAL_STATE__ or window.__STORE__ from rendered HTML."""
    for pattern in [
        r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});',
        r'window\.__STORE__\s*=\s*(\{.*?\});',
        r'"listings"\s*:\s*(\[.*?\])',
    ]:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
    return None


def _parse_price(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else None
    s = str(val).replace(",", "").replace(".", "").replace("€", "").replace("$", "").strip()
    # Handle European format (1.234,00 → 123400 → wrong, need to keep 1234)
    raw = re.sub(r"[^\d]", "", s)
    try:
        v = float(raw)
        return v if v > 500 else None  # sanity: listings < 500€ are bogus
    except ValueError:
        return None


def _parse_mileage(val: Any) -> Optional[int]:
    if val is None:
        return None
    s = str(val)
    raw = re.sub(r"[^\d]", "", s)
    try:
        v = int(raw)
        return v if 0 <= v < 2_000_000 else None
    except ValueError:
        return None


def _extract_listings_from_json_ld(json_lds: List[Dict]) -> List[Dict]:
    """Extract listing dicts from JSON-LD structured data."""
    listings = []

    def _walk(obj):
        if isinstance(obj, dict):
            t = obj.get("@type", "")
            types = [t] if isinstance(t, str) else t
            if any(x in ("Car", "Vehicle", "Product", "Offer", "BuyAction") for x in types):
                listings.append(obj)
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    for jld in json_lds:
        _walk(jld)

    return listings


def _extract_next_data_listings(html: str) -> List[Dict]:
    """Extract listings from AutoScout24's __NEXT_DATA__ JSON blob (most reliable)."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []

    def _find_listings(d, depth=0):
        if depth > 12:
            return []
        if isinstance(d, dict):
            if "listings" in d and isinstance(d["listings"], list) and d["listings"]:
                # Verify it looks like actual listing objects (have 'vehicle' key)
                if any("vehicle" in item or "price" in item for item in d["listings"]):
                    return d["listings"]
            for v in d.values():
                result = _find_listings(v, depth + 1)
                if result:
                    return result
        elif isinstance(d, list):
            for item in d:
                result = _find_listings(item, depth + 1)
                if result:
                    return result
        return []

    return _find_listings(data)


def _extract_listings_from_html(html: str, source_url: str) -> List[Dict]:
    """
    Fallback HTML extraction using BeautifulSoup for AutoScout24 listing cards.
    AutoScout24 renders listing cards as <article data-testid="regular-ad"> elements.
    """
    results = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # AutoScout24 listing articles
        cards = soup.find_all("article", attrs={"data-testid": re.compile(r"ad|listing", re.I)})
        if not cards:
            cards = soup.find_all("article")

        base_domain = urlparse(source_url).scheme + "://" + urlparse(source_url).netloc

        for card in cards[:30]:
            item = {}

            # Title / model info
            title_el = card.find(["h2", "h3", "h1"]) or card.find(class_=re.compile(r"title|name|model", re.I))
            if title_el:
                item["title"] = title_el.get_text(strip=True)

            # Price
            price_el = card.find(class_=re.compile(r"price|amount", re.I)) or card.find(attrs={"data-testid": re.compile(r"price", re.I)})
            if price_el:
                item["price_raw"] = price_el.get_text(strip=True)

            # Mileage
            mileage_el = card.find(attrs={"data-testid": re.compile(r"mileage|km", re.I)}) or card.find(class_=re.compile(r"mileage|km", re.I))
            if mileage_el:
                item["mileage_raw"] = mileage_el.get_text(strip=True)

            # Link
            link_el = card.find("a", href=True)
            if link_el:
                href = link_el["href"]
                if href.startswith("/"):
                    href = base_domain + href
                item["link"] = href

            # Location
            loc_el = card.find(attrs={"data-testid": re.compile(r"location|city", re.I)})
            if loc_el:
                item["location"] = loc_el.get_text(strip=True)

            if item.get("title") and (item.get("link") or item.get("price_raw")):
                results.append(item)

    except Exception as e:
        logger.warning("HTML extraction error: %s", e)

    return results


def _normalize_json_ld_listing(raw: Dict, source_url: str) -> Optional[Dict]:
    """Normalize a JSON-LD Car/Product/Offer object into a standard listing dict."""
    name = raw.get("name") or raw.get("description", "")[:100]
    if not name:
        return None

    # Extract price from offers
    price = None
    currency = "EUR"
    offers = raw.get("offers") or {}
    if isinstance(offers, list) and offers:
        offers = offers[0]
    if isinstance(offers, dict):
        price = _parse_price(offers.get("price"))
        currency = offers.get("priceCurrency") or "EUR"
    elif "price" in raw:
        price = _parse_price(raw["price"])

    # Brand and model from JSON-LD
    brand = None
    brand_obj = raw.get("brand") or raw.get("manufacturer") or {}
    if isinstance(brand_obj, dict):
        brand = brand_obj.get("name")
    elif isinstance(brand_obj, str):
        brand = brand_obj

    model_name = raw.get("model") or raw.get("vehicleModelDate") or name

    # Mileage
    mileage = _parse_mileage(
        raw.get("mileageFromOdometer", {}).get("value")
        if isinstance(raw.get("mileageFromOdometer"), dict)
        else raw.get("mileageFromOdometer")
    )

    # Year
    year = None
    year_raw = raw.get("vehicleModelDate") or raw.get("modelDate") or raw.get("year")
    if year_raw:
        m = re.search(r"(19|20)\d{2}", str(year_raw))
        if m:
            year = int(m.group())

    # Location
    city = None
    country = "Germany"
    loc = raw.get("itemOffered", {}) or {}
    if isinstance(raw.get("areaServed"), dict):
        city = raw["areaServed"].get("name")
    elif isinstance(raw.get("location"), dict):
        city = raw["location"].get("name")

    # URL
    url = raw.get("url") or raw.get("@id") or source_url

    fuel = raw.get("fuelType")
    transmission = raw.get("vehicleTransmission")
    color = raw.get("color")

    return {
        "brand": brand,
        "model": model_name,
        "title": name,
        "url": url,
        "price": price,
        "currency": currency,
        "mileage": mileage,
        "year": year,
        "city": city,
        "country": country,
        "fuel_type": fuel,
        "transmission": transmission,
        "color": color,
    }


def _normalize_next_data_listing(raw: Dict) -> Optional[Dict]:
    """Normalize an AutoScout24 __NEXT_DATA__ listing item."""
    vehicle = raw.get("vehicle") or {}
    brand = vehicle.get("make") or "Unknown"
    model_name = vehicle.get("modelGroup") or vehicle.get("model") or "Unknown"
    title = f"{brand} {model_name}".strip()
    if vehicle.get("modelVersionInput"):
        title = f"{brand} {model_name} {vehicle['modelVersionInput']}"

    # Price: priceFormatted = "€ 14,880" → strip non-numeric
    price_obj = raw.get("price") or {}
    price_raw = price_obj.get("priceFormatted") or price_obj.get("price") or ""
    price = _parse_price(price_raw)

    # Mileage from vehicle.mileageInKm or vehicleDetails
    mileage_raw = vehicle.get("mileageInKm") or ""
    mileage = _parse_mileage(mileage_raw)
    if mileage is None:
        for detail in raw.get("vehicleDetails") or []:
            if detail.get("iconName") == "mileage_odometer":
                mileage = _parse_mileage(detail.get("data"))
                break

    # Registration year from vehicleDetails calendar entry
    year = None
    for detail in raw.get("vehicleDetails") or []:
        if detail.get("iconName") == "calendar":
            date_str = detail.get("data") or ""  # e.g. "05/2021"
            m = re.search(r"(19|20)\d{2}", date_str)
            if m:
                year = int(m.group())
                break

    # Location
    loc_obj = raw.get("location") or {}
    city = loc_obj.get("city")
    country_code = loc_obj.get("countryCode") or "DE"
    _country_map = {"DE": "Germany", "FR": "France", "IT": "Italy", "ES": "Spain",
                    "NL": "Netherlands", "BE": "Belgium", "AT": "Austria", "PL": "Poland",
                    "GB": "UK", "SE": "Sweden", "CH": "Switzerland", "PT": "Portugal"}
    country = _country_map.get(country_code, country_code)

    # URL — AutoScout24 relative path
    url_path = raw.get("url") or ""
    url = f"https://www.autoscout24.com{url_path}" if url_path.startswith("/") else url_path

    fuel = vehicle.get("fuel")
    transmission = vehicle.get("transmission")

    return {
        "brand": brand,
        "model": model_name,
        "title": title[:200],
        "url": url,
        "price": price,
        "currency": "EUR",
        "mileage": mileage,
        "year": year,
        "city": city,
        "country": country,
        "fuel_type": fuel,
        "transmission": transmission,
        "color": None,
    }


def _normalize_html_listing(raw: Dict, source_url: str) -> Optional[Dict]:
    """Normalize a BeautifulSoup-extracted listing dict."""
    title = raw.get("title", "")
    if not title:
        return None

    # Try to infer brand from title
    known_brands = ["Toyota", "Volkswagen", "VW", "BMW", "Mercedes", "Audi", "Ford",
                    "Honda", "Hyundai", "Kia", "Renault", "Peugeot", "Tesla",
                    "Volvo", "Nissan", "Mazda", "Skoda", "Seat", "Opel"]
    brand = None
    for b in known_brands:
        if b.lower() in title.lower():
            brand = b
            break
    brand = brand or "Unknown"

    # Location parsing (city, country from "City, Country" format)
    city, country = None, "Germany"
    loc_text = raw.get("location", "")
    if "," in loc_text:
        parts = [p.strip() for p in loc_text.split(",")]
        city = parts[0] if parts else None
        country = parts[-1] if len(parts) > 1 else "Germany"

    # Year from title
    year = None
    m = re.search(r"(19|20)\d{2}", title)
    if m:
        year = int(m.group())

    return {
        "brand": brand,
        "model": title[:150],
        "title": title,
        "url": raw.get("link") or source_url,
        "price": _parse_price(raw.get("price_raw")),
        "currency": "EUR",
        "mileage": _parse_mileage(raw.get("mileage_raw")),
        "year": year,
        "city": city,
        "country": country,
        "fuel_type": None,
        "transmission": None,
        "color": None,
    }


# ---------------------------------------------------------------------------
# Database persistence
# ---------------------------------------------------------------------------

def _get_or_create_source(session):
    from database.models import ReviewSource
    src = session.query(ReviewSource).filter_by(name=_SOURCE_NAME).first()
    if src:
        return src
    src = ReviewSource(
        name=_SOURCE_NAME,
        base_url=_SOURCE_BASE,
        reliability_score=_RELIABILITY_SCORE,
        is_active=True,
    )
    session.add(src)
    session.flush()
    return src


def _get_or_create_model(session, brand_name: str, model_name: str):
    from database.models import CarBrand, CarModel
    brand_name = (brand_name or "Unknown")[:100]
    model_name = (model_name or "Unknown")[:150]
    brand = session.query(CarBrand).filter_by(name=brand_name).first()
    if not brand:
        brand = CarBrand(name=brand_name)
        session.add(brand)
        session.flush()
    current_year = datetime.now(timezone.utc).year
    model = session.query(CarModel).filter_by(brand_id=brand.id, name=model_name).first()
    if not model:
        model = CarModel(brand_id=brand.id, name=model_name, year=current_year)
        session.add(model)
        session.flush()
    return model


def _store_listing(session, norm: Dict, source) -> bool:
    from database.models import CarListing
    url = norm["url"]
    if not url or len(url) < 10:
        return False
    # Dedup on listing_url
    if session.query(CarListing).filter_by(listing_url=url).first():
        return False

    model = _get_or_create_model(session, norm.get("brand"), norm.get("model"))
    listing = CarListing(
        model_id=model.id,
        source_id=source.id,
        listing_url=url,
        listed_price=norm.get("price"),
        currency=norm.get("currency") or "EUR",
        mileage_km=norm.get("mileage"),
        city=norm.get("city"),
        country=norm.get("country"),
        listed_at=date.today(),
        is_active=True,
        fuel_type=norm.get("fuel_type"),
        transmission=norm.get("transmission"),
        color=norm.get("color"),
        listing_year=norm.get("year"),
        data_origin="scraped",
    )
    session.add(listing)
    session.flush()
    return True


def _store_raw_page(session, url: str, html: str):
    from database.models import RawPage
    content_hash = hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()
    from database.models import RawPage
    if session.query(RawPage).filter_by(content_hash=content_hash).first():
        return
    domain = urlparse(url).netloc
    session.add(RawPage(
        source_url=url,
        source_domain=domain,
        http_status_code=200,
        raw_html=html,
        content_hash=content_hash,
        scraper_version="playwright-listings-1.0",
        is_parsed=True,
        scraped_at=datetime.now(timezone.utc),
    ))
    session.flush()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_listings_ingest(max_pages: int = 4, max_per_page: int = 20) -> Dict:
    from database.connection import get_db_session

    metrics = {
        "pages_fetched": 0,
        "listings_inserted": 0,
        "listings_skipped": 0,
        "extraction_method": [],
    }

    sep = "=" * 56
    logger.info(sep)
    logger.info("Listings Ingest starting — max_pages=%d, max_per_page=%d", max_pages, max_per_page)
    logger.info(sep)

    urls_to_fetch = SEARCH_URLS[:max_pages]

    for url in urls_to_fetch:
        logger.info("── Fetching: %s", url)
        html = _fetch_rendered_html(url)
        if not html:
            logger.warning("   No HTML retrieved for %s", url)
            continue

        metrics["pages_fetched"] += 1

        normalized: List[Dict] = []
        method = "none"

        # Priority 1: __NEXT_DATA__ (AutoScout24 full listing JSON — most reliable)
        next_listings = _extract_next_data_listings(html)
        if next_listings:
            method = "__next_data__"
            logger.info("   __NEXT_DATA__ listings found: %d", len(next_listings))
            for raw_item in next_listings[:max_per_page]:
                norm = _normalize_next_data_listing(raw_item)
                if norm:
                    normalized.append(norm)

        # Priority 2: JSON-LD (schema.org Car/Offer objects)
        if not normalized:
            json_lds = _extract_json_ld(html)
            jld_listings = _extract_listings_from_json_ld(json_lds)
            logger.info("   JSON-LD Car objects found: %d", len(jld_listings))
            if jld_listings:
                method = "json-ld"
                for raw_item in jld_listings[:max_per_page]:
                    norm = _normalize_json_ld_listing(raw_item, url)
                    if norm:
                        normalized.append(norm)

        # Priority 3: HTML card extraction (last resort)
        if not normalized:
            logger.info("   Falling back to HTML card extraction")
            html_listings = _extract_listings_from_html(html, url)
            logger.info("   HTML cards found: %d", len(html_listings))
            method = "html"
            for raw_item in html_listings[:max_per_page]:
                norm = _normalize_html_listing(raw_item, url)
                if norm:
                    normalized.append(norm)

        metrics["extraction_method"].append(method)
        logger.info("   Extracted %d normalized listings via %s", len(normalized), method)

        inserted = 0
        skipped = 0
        try:
            with get_db_session() as session:
                _store_raw_page(session, url, html)
                source = _get_or_create_source(session)
                for norm in normalized:
                    try:
                        if _store_listing(session, norm, source):
                            inserted += 1
                        else:
                            skipped += 1
                    except Exception as e:
                        logger.warning("   Store error for listing: %s", e)
                        session.rollback()
                session.commit()
        except Exception as e:
            logger.error("   DB error: %s", e)

        metrics["listings_inserted"] += inserted
        metrics["listings_skipped"] += skipped
        logger.info("   Inserted=%d  Skipped=%d", inserted, skipped)

        time.sleep(3)

    logger.info(sep)
    logger.info("Listings Ingest complete")
    logger.info("  Pages fetched    : %d", metrics["pages_fetched"])
    logger.info("  Listings inserted: %d", metrics["listings_inserted"])
    logger.info("  Listings skipped : %d (duplicates)", metrics["listings_skipped"])
    logger.info(sep)

    return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args():
    parser = argparse.ArgumentParser(description="Ingest real car listings via AutoScout24 Playwright.")
    parser.add_argument("--pages", type=int, default=4, help="Number of search pages to scrape (default: 4)")
    parser.add_argument("--max-per-page", type=int, default=20, help="Max listings per page (default: 20)")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_listings_ingest(max_pages=args.pages, max_per_page=args.max_per_page)
