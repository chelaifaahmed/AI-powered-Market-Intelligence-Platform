#!/usr/bin/env python3
"""
scripts/run_reviews_ingest.py
------------------------------
Ingests real consumer car brand reviews from Trustpilot using Playwright.

Trustpilot brand pages contain 20+ consumer review cards with:
  - star rating (1-5)
  - review title
  - review text
  - author name
  - ISO 8601 datetime

These are mapped to car_reviews with brand→model association.

Pipeline:
  1. Playwright fetches rendered Trustpilot brand review pages
  2. BeautifulSoup extracts review cards via data-service-review-card-paper
  3. Reviews stored in `car_reviews` with `data_origin='scraped'`
  4. NLP pipeline runs on new reviews immediately

Usage:
    python scripts/run_reviews_ingest.py [--max-per-page 25]
"""

from __future__ import annotations

import hashlib
import logging
import os
import random
import re
import sys
import time
from datetime import date, datetime, timezone
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
logger = logging.getLogger("scripts.reviews_ingest")

# ---------------------------------------------------------------------------
# Pagination config
# ---------------------------------------------------------------------------
MAX_PAGES = 5  # Scrape up to 5 pages per brand (Trustpilot shows ~20 reviews/page)

# ---------------------------------------------------------------------------
# Source registry — Trustpilot brand pages
# Each entry: (brand_name, model_hint, trustpilot_url)
# model_hint is used to find/create a generic CarModel for brand-level reviews
# ---------------------------------------------------------------------------
REVIEW_SOURCES = [
    # Original brands
    ("Toyota", "General", "https://www.trustpilot.com/review/www.toyota.com"),
    ("Ford", "General", "https://www.trustpilot.com/review/www.ford.com"),
    ("BMW", "General", "https://www.trustpilot.com/review/www.bmw.com"),
    ("Hyundai", "General", "https://www.trustpilot.com/review/www.hyundai.com"),
    ("Honda", "General", "https://www.trustpilot.com/review/www.honda.com"),
    ("Volkswagen", "General", "https://www.trustpilot.com/review/www.volkswagen.com"),
    ("Tesla", "General", "https://www.trustpilot.com/review/www.tesla.com"),
    ("Kia", "General", "https://www.trustpilot.com/review/www.kia.com"),
    # EU car brands
    ("Renault", "General", "https://www.trustpilot.com/review/www.renault.com"),
    ("Peugeot", "General", "https://www.trustpilot.com/review/www.peugeot.com"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _content_hash(source_url: str, review_text: str) -> str:
    raw = f"{source_url}|{review_text}".encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()


def _parse_iso_date(dt_str: str) -> Optional[date]:
    """Parse ISO 8601 datetime string to date."""
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


# ---------------------------------------------------------------------------
# Trustpilot review extraction
# ---------------------------------------------------------------------------

def _extract_trustpilot_reviews(html: str) -> list[dict]:
    """Extract review cards from Trustpilot page HTML.

    Trustpilot review card structure:
      - Container: element with data-service-review-card-paper attribute
      - Rating: <img alt="Rated X out of 5 stars">
      - Title: <h2> inside card
      - Body: longest <p> with >30 chars
      - Author: <span data-consumer-name-typography>
      - Date: <time datetime="ISO8601">
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    reviews = []

    cards = soup.find_all(attrs={"data-service-review-card-paper": True})
    if not cards:
        # Fallback: look for article elements with review content
        cards = soup.find_all("article", class_=re.compile(r"review", re.I))

    for card in cards:
        review = _parse_trustpilot_card(card)
        if review and review.get("review_text") and len(review["review_text"]) > 20:
            reviews.append(review)

    return reviews


def _parse_trustpilot_card(card) -> dict:
    """Parse one Trustpilot review card."""
    # Rating: img alt="Rated X out of 5 stars"
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

    # Title: <h2> inside card
    title = ""
    h2 = card.find("h2")
    if h2:
        title = h2.get_text(strip=True)

    # Body text: longest <p> with substantial content
    body = ""
    p_tags = card.find_all("p")
    for p in p_tags:
        txt = p.get_text(strip=True)
        if len(txt) > len(body):
            body = txt

    # Author: span with data-consumer-name-typography
    author = None
    author_el = card.find("span", attrs={"data-consumer-name-typography": True})
    if author_el:
        author = author_el.get_text(strip=True)

    # Date: <time datetime="ISO8601">
    review_date = None
    time_el = card.find("time")
    if time_el:
        dt_attr = time_el.get("datetime", "")
        review_date = _parse_iso_date(dt_attr)

    return {
        "review_title": title,
        "review_text": body,
        "rating": rating,
        "author": author,
        "review_date": review_date,
    }


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------

def _log_failure(session, source_url: str, entity_type: str, error_msg: str):
    """Persist a failure to the DataQualityLog dead-letter table."""
    from database.models import DataQualityLog
    try:
        session.add(DataQualityLog(
            source_url=source_url,
            entity_type=entity_type,
            validation_error=error_msg,
        ))
        session.flush()
    except Exception:
        logger.debug("Could not persist failure log entry", exc_info=True)


def _brand_recently_scraped(session, brand_name: str, hours: int = 12) -> bool:
    """Return True if we already have scraped reviews for this brand within `hours`."""
    from database.models import CarReview, CarModel, CarBrand
    cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(hours=hours)
    recent = (
        session.query(CarReview.id)
        .join(CarModel, CarReview.model_id == CarModel.id)
        .join(CarBrand, CarModel.brand_id == CarBrand.id)
        .filter(
            CarBrand.name.ilike(brand_name),
            CarReview.data_origin == "scraped",
            CarReview.scraped_at >= cutoff,
        )
        .limit(1)
        .first()
    )
    return recent is not None


def _record_step_run(session, stats: dict, started: datetime, status: str):
    """Write a PipelineStepRun row for this ingestion."""
    from database.models import PipelineStepRun
    from database.enums import PipelineStatus
    finished = datetime.now(timezone.utc)
    duration_ms = int((finished - started).total_seconds() * 1000)
    step = PipelineStepRun(
        step_name="reviews_ingest_trustpilot",
        status=PipelineStatus(status),
        started_at=started,
        finished_at=finished,
        duration_ms=duration_ms,
        records_seen=stats["reviews_found"],
        records_processed=stats["reviews_inserted"],
        records_skipped=stats["reviews_duplicate"] + stats.get("reviews_fresh_skip", 0),
        records_failed=stats["reviews_failed"],
        records_inserted=stats["reviews_inserted"],
        error_count=stats["reviews_failed"],
        step_metadata={
            "pages_fetched": stats["pages_fetched"],
            "nlp_processed": stats["nlp_processed"],
            "brands_skipped_fresh": stats.get("reviews_fresh_skip", 0),
        },
    )
    session.add(step)


def ingest_reviews(max_per_page: int = 25, freshness_hours: int = 12) -> dict:
    """Fetch and ingest real consumer reviews from Trustpilot."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    from database.connection import get_db_session
    from database.models import CarReview, RawPage
    from nlp.nlp_pipeline import NlpPipeline

    run_started = datetime.now(timezone.utc)
    stats = {
        "pages_fetched": 0,
        "reviews_found": 0,
        "reviews_inserted": 0,
        "reviews_duplicate": 0,
        "reviews_failed": 0,
        "reviews_fresh_skip": 0,
        "nlp_processed": 0,
    }

    logger.info(
        "Starting Trustpilot review ingestion — %d brands, up to %d pages each",
        len(REVIEW_SOURCES), MAX_PAGES,
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

        for brand_name, model_hint, base_url in REVIEW_SOURCES:
            # Freshness check — skip if recently scraped
            with get_db_session() as session:
                if _brand_recently_scraped(session, brand_name, hours=freshness_hours):
                    logger.info("Skipping %s — scraped within last %dh", brand_name, freshness_hours)
                    stats["reviews_fresh_skip"] += 1
                    continue

            brand_total_new = 0
            brand_failed = False

            # ------ Paginate through up to MAX_PAGES pages per brand ------
            for page_num in range(1, MAX_PAGES + 1):
                url = f"{base_url}?page={page_num}"
                logger.info("Scraping %s page %d/%d — %s", brand_name, page_num, MAX_PAGES, url)

                try:
                    resp = page.goto(url, timeout=25000, wait_until="domcontentloaded")
                    http_status = resp.status if resp else None

                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except PWTimeout:
                        pass

                    # Dismiss cookie banners (only needed on page 1 typically)
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

                    # Scroll to load all review cards
                    for _ in range(4):
                        page.evaluate("window.scrollBy(0, window.innerHeight)")
                        page.wait_for_timeout(600)

                    html = page.content()
                    stats["pages_fetched"] += 1
                    logger.info(
                        "Fetched %s - status=%s, size=%d chars",
                        url, http_status, len(html),
                    )

                    if http_status and http_status >= 400:
                        logger.warning("HTTP %s for %s — stopping pagination", http_status, url)
                        brand_failed = True
                        break

                except PWTimeout:
                    logger.warning("Timeout fetching %s — stopping pagination", url)
                    stats["reviews_failed"] += 1
                    with get_db_session() as session:
                        _log_failure(session, url, "car_review", f"Timeout fetching Trustpilot page: {url}")
                    break
                except Exception as exc:
                    logger.error("Failed fetching %s: %s — stopping pagination", url, exc)
                    stats["reviews_failed"] += 1
                    with get_db_session() as session:
                        _log_failure(session, url, "car_review", f"Fetch error: {exc}")
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
                        scraper_version="reviews-ingest-1.1",
                        is_parsed=True,
                        scraped_at=datetime.now(timezone.utc),
                    ))

                # Extract reviews
                raw_reviews = _extract_trustpilot_reviews(html)
                page_review_count = len(raw_reviews)
                stats["reviews_found"] += page_review_count
                logger.info(
                    "Scraping %s page %d/%d — found %d reviews",
                    brand_name, page_num, MAX_PAGES, page_review_count,
                )

                if not raw_reviews:
                    logger.info("No reviews on page %d — stopping pagination for %s", page_num, brand_name)
                    break

                # Store reviews
                page_new = 0
                with get_db_session() as session:
                    brand = _get_or_create_brand(session, brand_name)
                    car_model = _get_or_create_model(session, brand, model_hint)

                    for rev in raw_reviews[:max_per_page]:
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

                # Random delay between pages to avoid rate limiting
                if page_num < MAX_PAGES and raw_reviews:
                    delay = random.uniform(3, 7)
                    logger.info("Waiting %.1fs before next page...", delay)
                    time.sleep(delay)

            # End pagination loop for this brand
            logger.info("Inserted %d new reviews for %s (across %d pages)", brand_total_new, brand_name, MAX_PAGES)

            if brand_failed:
                logger.warning("Brand %s had HTTP errors — logged as WARNING", brand_name)

            # Run NLP on new reviews for this brand
            if brand_total_new > 0:
                logger.info("Running NLP on %d new reviews...", brand_total_new)
                try:
                    with get_db_session() as session:
                        nlp = NlpPipeline(session)
                        nlp_metrics = nlp.process_car_reviews(limit=brand_total_new + 10)
                        stats["nlp_processed"] += nlp_metrics.get("records_processed", 0)
                        logger.info("NLP: %s", nlp_metrics)
                except Exception as exc:
                    logger.error("NLP failed: %s", exc)

            # Polite delay between brands
            time.sleep(3)

        page.close()
        context.close()
        browser.close()

    # Record step run for observability
    run_status = "success" if stats["reviews_failed"] == 0 else (
        "partial" if stats["reviews_inserted"] > 0 else "failed"
    )
    try:
        with get_db_session() as session:
            _record_step_run(session, stats, run_started, run_status)
        logger.info("Recorded PipelineStepRun (status=%s)", run_status)
    except Exception as exc:
        logger.warning("Could not record step run: %s", exc)

    # Summary
    logger.info("=" * 60)
    logger.info("Review Ingestion Summary")
    logger.info("=" * 60)
    logger.info("Pages fetched:     %d", stats["pages_fetched"])
    logger.info("Brands skipped:    %d (freshness)", stats["reviews_fresh_skip"])
    logger.info("Reviews found:     %d", stats["reviews_found"])
    logger.info("Reviews inserted:  %d", stats["reviews_inserted"])
    logger.info("Reviews duplicate: %d", stats["reviews_duplicate"])
    logger.info("Reviews failed:    %d", stats["reviews_failed"])
    logger.info("NLP processed:     %d", stats["nlp_processed"])
    logger.info("=" * 60)

    return stats


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Ingest real consumer car reviews from Trustpilot")
    ap.add_argument("--max-per-page", type=int, default=25, help="Max reviews per page")
    ap.add_argument("--freshness-hours", type=int, default=12,
                    help="Skip brands scraped within this many hours (0 = always scrape)")
    args = ap.parse_args()
    ingest_reviews(max_per_page=args.max_per_page, freshness_hours=args.freshness_hours)
