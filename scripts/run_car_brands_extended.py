#!/usr/bin/env python3
"""
scripts/run_car_brands_extended.py
-----------------------------------
Re-scrapes car brands that have < 100 real reviews on Trustpilot.
Also scrapes brands with 0 reviews that have confirmed Trustpilot URLs.

Uses the same Playwright + BeautifulSoup extraction as run_reviews_ingest.py.
Scrapes up to 7 pages per brand to try to get 100+ reviews.

Usage:
    python scripts/run_car_brands_extended.py [--max-pages 7] [--min-reviews 100]
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("scripts.car_brands_extended")

# ---------------------------------------------------------------------------
# Brand → Trustpilot URL mapping
# Includes all brands we want to scrape (or re-scrape for more reviews)
# ---------------------------------------------------------------------------
BRAND_URLS = {
    # Already in REVIEW_SOURCES but may need more pages
    "Toyota": "https://www.trustpilot.com/review/www.toyota.com",
    "Ford": "https://www.trustpilot.com/review/www.ford.com",
    "BMW": "https://www.trustpilot.com/review/www.bmw.com",
    "Hyundai": "https://www.trustpilot.com/review/www.hyundai.com",
    "Honda": "https://www.trustpilot.com/review/www.honda.com",
    "Volkswagen": "https://www.trustpilot.com/review/www.volkswagen.com",
    "Tesla": "https://www.trustpilot.com/review/www.tesla.com",
    "Kia": "https://www.trustpilot.com/review/www.kia.com",
    "Renault": "https://www.trustpilot.com/review/www.renault.com",
    "Peugeot": "https://www.trustpilot.com/review/www.peugeot.com",
    # Brands with 0 reviews — confirmed on Trustpilot
    "Mercedes": "https://www.trustpilot.com/review/www.mercedes-benz.com",
    "Audi": "https://www.trustpilot.com/review/www.audi.com",
    "Nissan": "https://www.trustpilot.com/review/www.nissan.com",
    "Volvo": "https://www.trustpilot.com/review/www.volvocars.com",
    "Land Rover": "https://www.trustpilot.com/review/www.landrover.com",
    "Mazda": "https://www.trustpilot.com/review/www.mazda.co.uk",
    "Subaru": "https://www.trustpilot.com/review/www.subaru.com",
    "Jeep": "https://www.trustpilot.com/review/www.jeep.com",
    "Porsche": "https://www.trustpilot.com/review/www.porsche.com",
    "Chevrolet": "https://www.trustpilot.com/review/www.chevrolet.com",
    "Fiat": "https://www.trustpilot.com/review/www.fiat.com",
}


# ---------------------------------------------------------------------------
# Helpers (same as run_reviews_ingest.py)
# ---------------------------------------------------------------------------

def _content_hash(source_url: str, review_text: str) -> str:
    raw = f"{source_url}|{review_text}".encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()


def _parse_iso_date(dt_str: str) -> Optional[date]:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        pass
    try:
        return datetime.strptime(dt_str[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _get_or_create_brand(session, brand_name: str):
    from database.models import CarBrand
    brand = session.query(CarBrand).filter(
        CarBrand.name.ilike(brand_name)
    ).first()
    if brand:
        return brand
    brand = CarBrand(name=brand_name, is_active=True)
    session.add(brand)
    session.flush()
    logger.info("Created brand: %s", brand_name)
    return brand


def _get_or_create_model(session, brand, model_name: str):
    from database.models import CarModel
    model = session.query(CarModel).filter(
        CarModel.brand_id == brand.id,
        CarModel.name.ilike(model_name),
    ).first()
    if model:
        return model
    model = CarModel(brand_id=brand.id, name=model_name, is_active=True)
    session.add(model)
    session.flush()
    logger.info("Created model: %s %s", brand.name, model_name)
    return model


def _extract_trustpilot_reviews(html: str) -> list[dict]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    reviews = []

    cards = soup.find_all(attrs={"data-service-review-card-paper": True})
    if not cards:
        cards = soup.find_all("article", class_=re.compile(r"review", re.I))

    for card in cards:
        review = _parse_trustpilot_card(card)
        if review and review.get("review_text") and len(review["review_text"]) > 20:
            reviews.append(review)

    return reviews


def _parse_trustpilot_card(card) -> dict:
    rating = None
    img = card.find("img", alt=re.compile(r"Rated\s+\d", re.I))
    if img:
        m = re.search(r"Rated\s+(\d+)\s+out\s+of\s+(\d+)", img.get("alt", ""))
        if m:
            val = float(m.group(1))
            base = float(m.group(2))
            if base == 10:
                val = val / 2.0
            rating = min(max(val, 1.0), 5.0)

    title = ""
    h2 = card.find("h2")
    if h2:
        title = h2.get_text(strip=True)

    body = ""
    for p in card.find_all("p"):
        txt = p.get_text(strip=True)
        if len(txt) > len(body):
            body = txt

    author = None
    author_el = card.find("span", attrs={"data-consumer-name-typography": True})
    if author_el:
        author = author_el.get_text(strip=True)

    review_date = None
    time_el = card.find("time")
    if time_el:
        review_date = _parse_iso_date(time_el.get("datetime", ""))

    return {
        "review_title": title,
        "review_text": body,
        "rating": rating,
        "author": author,
        "review_date": review_date,
    }


def _get_brand_review_count(session, brand_name: str) -> int:
    """Count existing scraped reviews for a brand."""
    from database.models import CarReview, CarModel, CarBrand
    count = (
        session.query(CarReview.id)
        .join(CarModel, CarReview.model_id == CarModel.id)
        .join(CarBrand, CarModel.brand_id == CarBrand.id)
        .filter(
            CarBrand.name.ilike(brand_name),
            CarReview.data_origin == "scraped",
        )
        .count()
    )
    return count


def _log_failure(session, source_url: str, error_msg: str):
    from database.models import DataQualityLog
    try:
        session.add(DataQualityLog(
            source_url=source_url,
            entity_type="car_review",
            validation_error=error_msg,
        ))
        session.flush()
    except Exception:
        logger.debug("Could not persist failure log entry", exc_info=True)


def _record_step_run(session, stats: dict, started: datetime, status: str):
    from database.models import PipelineStepRun
    from database.enums import PipelineStatus
    finished = datetime.now(timezone.utc)
    duration_ms = int((finished - started).total_seconds() * 1000)
    step = PipelineStepRun(
        step_name="car_brands_extended_scrape",
        status=PipelineStatus(status),
        started_at=started,
        finished_at=finished,
        duration_ms=duration_ms,
        records_seen=stats["reviews_found"],
        records_processed=stats["reviews_inserted"],
        records_skipped=stats["reviews_duplicate"] + stats.get("brands_skipped", 0),
        records_failed=stats["reviews_failed"],
        records_inserted=stats["reviews_inserted"],
        error_count=stats["reviews_failed"],
        step_metadata={
            "pages_fetched": stats["pages_fetched"],
            "brands_scraped": stats["brands_scraped"],
            "brands_skipped": stats.get("brands_skipped", 0),
        },
    )
    session.add(step)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def ingest_extended_brands(max_pages: int = 7, min_reviews: int = 100) -> dict:
    """Scrape brands with fewer than min_reviews real reviews."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    from database.connection import get_db_session
    from database.models import CarReview, RawPage

    run_started = datetime.now(timezone.utc)
    stats = {
        "pages_fetched": 0,
        "reviews_found": 0,
        "reviews_inserted": 0,
        "reviews_duplicate": 0,
        "reviews_failed": 0,
        "brands_scraped": 0,
        "brands_skipped": 0,
    }

    # Determine which brands need more reviews
    brands_to_scrape = []
    with get_db_session() as session:
        for brand_name, tp_url in BRAND_URLS.items():
            count = _get_brand_review_count(session, brand_name)
            if count < min_reviews:
                brands_to_scrape.append((brand_name, tp_url, count))
                logger.info("Will scrape %s — %d reviews (need %d)", brand_name, count, min_reviews)
            else:
                stats["brands_skipped"] += 1
                logger.info("Skipping %s — already has %d reviews", brand_name, count)

    if not brands_to_scrape:
        logger.info("All brands have >= %d reviews. Nothing to scrape.", min_reviews)
        return stats

    logger.info(
        "Starting extended scrape — %d brands need more reviews, up to %d pages each",
        len(brands_to_scrape), max_pages,
    )

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()

        for brand_name, base_url, existing_count in brands_to_scrape:
            brand_total_new = 0

            for page_num in range(1, max_pages + 1):
                url = f"{base_url}?page={page_num}"
                logger.info("Scraping %s page %d/%d — %s", brand_name, page_num, max_pages, url)

                try:
                    resp = page.goto(url, timeout=25000, wait_until="domcontentloaded")
                    http_status = resp.status if resp else None

                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except PWTimeout:
                        pass

                    if page_num == 1:
                        for sel in [
                            "#onetrust-accept-btn-handler",
                            "button[name='accept']",
                            "button:has-text('Accept')",
                            "button:has-text('I accept')",
                        ]:
                            try:
                                page.click(sel, timeout=2000)
                                break
                            except Exception:
                                pass

                    for _ in range(4):
                        page.evaluate("window.scrollBy(0, window.innerHeight)")
                        page.wait_for_timeout(600)

                    html = page.content()
                    stats["pages_fetched"] += 1

                    if http_status and http_status >= 400:
                        logger.warning("HTTP %s for %s — stopping", http_status, url)
                        break

                except PWTimeout:
                    logger.warning("Timeout fetching %s — stopping", url)
                    stats["reviews_failed"] += 1
                    with get_db_session() as session:
                        _log_failure(session, url, f"Timeout: {url}")
                    break
                except Exception as exc:
                    logger.error("Failed fetching %s: %s", url, exc)
                    stats["reviews_failed"] += 1
                    with get_db_session() as session:
                        _log_failure(session, url, f"Fetch error: {exc}")
                    break

                # Store raw HTML
                domain = urlparse(url).netloc
                with get_db_session() as session:
                    ch = hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()
                    session.add(RawPage(
                        source_url=url,
                        source_domain=domain,
                        http_status_code=http_status,
                        raw_html=html,
                        content_hash=ch,
                        scraper_version="car-brands-extended-1.0",
                        is_parsed=True,
                        scraped_at=datetime.now(timezone.utc),
                    ))

                # Extract reviews
                raw_reviews = _extract_trustpilot_reviews(html)
                page_review_count = len(raw_reviews)
                stats["reviews_found"] += page_review_count
                logger.info(
                    "Scraping %s page %d/%d — found %d reviews",
                    brand_name, page_num, max_pages, page_review_count,
                )

                if not raw_reviews:
                    logger.info("No reviews on page %d — stopping for %s", page_num, brand_name)
                    break

                # Store reviews
                page_new = 0
                with get_db_session() as session:
                    brand = _get_or_create_brand(session, brand_name)
                    car_model = _get_or_create_model(session, brand, "General")

                    for rev in raw_reviews[:25]:
                        text = (rev.get("review_text") or "").strip()
                        if not text or len(text) < 15:
                            continue

                        ch = _content_hash(url, text)
                        existing = session.query(CarReview).filter(
                            CarReview.content_hash == ch
                        ).first()
                        if existing:
                            stats["reviews_duplicate"] += 1
                            continue

                        try:
                            review = CarReview(
                                model_id=car_model.id,
                                source_url=url,
                                review_title=rev.get("review_title") or None,
                                review_text=text,
                                rating=(
                                    Decimal(str(rev["rating"]))
                                    if rev.get("rating") else None
                                ),
                                author=rev.get("author") or None,
                                review_date=rev.get("review_date"),
                                content_hash=ch,
                                data_origin="scraped",
                                is_processed=False,
                                scraped_at=datetime.now(timezone.utc),
                            )
                            session.add(review)
                            session.flush()
                            page_new += 1
                            stats["reviews_inserted"] += 1
                        except Exception as exc:
                            session.rollback()
                            logger.error("Failed inserting review: %s", exc)
                            stats["reviews_failed"] += 1

                brand_total_new += page_new

                # Delay between pages (4-8 seconds)
                if page_num < max_pages and raw_reviews:
                    delay = random.uniform(4, 8)
                    logger.info("Waiting %.1fs before next page...", delay)
                    time.sleep(delay)

            stats["brands_scraped"] += 1
            logger.info(
                "Inserted %d new reviews for %s (had %d, now ~%d)",
                brand_total_new, brand_name, existing_count, existing_count + brand_total_new,
            )

            # Polite delay between brands
            delay = random.uniform(3, 5)
            logger.info("Waiting %.1fs before next brand...", delay)
            time.sleep(delay)

        page.close()
        context.close()
        browser.close()

    # Record step run
    run_status = "success" if stats["reviews_failed"] == 0 else (
        "partial" if stats["reviews_inserted"] > 0 else "failed"
    )
    try:
        with get_db_session() as session:
            _record_step_run(session, stats, run_started, run_status)
    except Exception as exc:
        logger.warning("Could not record step run: %s", exc)

    # Summary
    logger.info("=" * 60)
    logger.info("Extended Car Brands Scrape Summary")
    logger.info("=" * 60)
    logger.info("Brands scraped:    %d", stats["brands_scraped"])
    logger.info("Brands skipped:    %d (already >= %d reviews)", stats["brands_skipped"], min_reviews)
    logger.info("Pages fetched:     %d", stats["pages_fetched"])
    logger.info("Reviews found:     %d", stats["reviews_found"])
    logger.info("Reviews inserted:  %d", stats["reviews_inserted"])
    logger.info("Reviews duplicate: %d", stats["reviews_duplicate"])
    logger.info("Reviews failed:    %d", stats["reviews_failed"])
    logger.info("=" * 60)

    return stats


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Extended car brand review scraping")
    ap.add_argument("--max-pages", type=int, default=7, help="Max pages per brand")
    ap.add_argument("--min-reviews", type=int, default=100,
                    help="Only scrape brands with fewer than this many reviews")
    args = ap.parse_args()
    ingest_extended_brands(max_pages=args.max_pages, min_reviews=args.min_reviews)
