#!/usr/bin/env python3
"""
scripts/run_insurance_scrape.py
-------------------------------
Scrapes real consumer insurance company reviews from Trustpilot using Playwright.

Follows the exact same pattern as run_reviews_ingest.py but targets
insurance_companies and stores results in insurance_reviews.

Pipeline:
  1. Queries insurance_companies where website (Trustpilot URL) IS NOT NULL
  2. Playwright fetches rendered Trustpilot review pages (up to MAX_PAGES per company)
  3. BeautifulSoup extracts review cards via data-service-review-card-paper
  4. Reviews stored in `insurance_reviews` with `data_origin='scraped'`

Usage:
    python scripts/run_insurance_scrape.py [--max-pages 5] [--freshness-hours 12]
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
logger = logging.getLogger("scripts.insurance_scrape")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MAX_PAGES = 5  # Up to 5 pages per company (~20 reviews/page)


# ---------------------------------------------------------------------------
# Helpers
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


# ---------------------------------------------------------------------------
# Trustpilot review extraction (reused from run_reviews_ingest.py)
# ---------------------------------------------------------------------------

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
    # Rating
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

    # Title
    title = ""
    h2 = card.find("h2")
    if h2:
        title = h2.get_text(strip=True)

    # Body
    body = ""
    for p in card.find_all("p"):
        txt = p.get_text(strip=True)
        if len(txt) > len(body):
            body = txt

    # Author
    author = None
    author_el = card.find("span", attrs={"data-consumer-name-typography": True})
    if author_el:
        author = author_el.get_text(strip=True)

    # Date
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


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------

def _company_recently_scraped(session, company_id, hours: int = 12) -> bool:
    from database.models import InsuranceReview
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent = (
        session.query(InsuranceReview.id)
        .filter(
            InsuranceReview.company_id == company_id,
            InsuranceReview.data_origin == "scraped",
            InsuranceReview.scraped_at >= cutoff,
        )
        .limit(1)
        .first()
    )
    return recent is not None


def _log_failure(session, source_url: str, error_msg: str):
    from database.models import DataQualityLog
    try:
        session.add(DataQualityLog(
            source_url=source_url,
            entity_type="insurance_review",
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
        step_name="insurance_reviews_scrape_trustpilot",
        status=PipelineStatus(status),
        started_at=started,
        finished_at=finished,
        duration_ms=duration_ms,
        records_seen=stats["reviews_found"],
        records_processed=stats["reviews_inserted"],
        records_skipped=stats["reviews_duplicate"] + stats.get("companies_skipped_fresh", 0),
        records_failed=stats["reviews_failed"],
        records_inserted=stats["reviews_inserted"],
        error_count=stats["reviews_failed"],
        step_metadata={
            "pages_fetched": stats["pages_fetched"],
            "companies_scraped": stats["companies_scraped"],
            "companies_skipped": stats.get("companies_skipped_fresh", 0),
        },
    )
    session.add(step)


def ingest_insurance_reviews(max_pages: int = 5, freshness_hours: int = 12) -> dict:
    """Fetch and ingest real insurance company reviews from Trustpilot."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    from database.connection import get_db_session
    from database.models import InsuranceCompany, InsuranceReview, RawPage

    run_started = datetime.now(timezone.utc)
    stats = {
        "pages_fetched": 0,
        "reviews_found": 0,
        "reviews_inserted": 0,
        "reviews_duplicate": 0,
        "reviews_failed": 0,
        "companies_scraped": 0,
        "companies_skipped_fresh": 0,
    }

    # Get all companies with Trustpilot URLs
    with get_db_session() as session:
        companies = session.query(InsuranceCompany).filter(
            InsuranceCompany.website.isnot(None),
            InsuranceCompany.website.like("%trustpilot.com%"),
        ).all()
        # Detach data we need
        targets = [(c.id, c.name, c.website) for c in companies]

    logger.info(
        "Starting insurance review scrape — %d companies with Trustpilot URLs, up to %d pages each",
        len(targets), max_pages,
    )

    if not targets:
        logger.warning("No insurance companies with Trustpilot URLs found. Exiting.")
        return stats

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

        for company_id, company_name, trustpilot_url in targets:
            # Freshness check
            with get_db_session() as session:
                if _company_recently_scraped(session, company_id, hours=freshness_hours):
                    logger.info("Skipping %s — scraped within last %dh", company_name, freshness_hours)
                    stats["companies_skipped_fresh"] += 1
                    continue

            company_total_new = 0
            company_failed = False

            for page_num in range(1, max_pages + 1):
                url = f"{trustpilot_url}?page={page_num}"
                logger.info("Scraping %s page %d/%d — %s", company_name, page_num, max_pages, url)

                try:
                    resp = page.goto(url, timeout=25000, wait_until="domcontentloaded")
                    http_status = resp.status if resp else None

                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except PWTimeout:
                        pass

                    # Cookie banner
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

                    # Scroll to load reviews
                    for _ in range(4):
                        page.evaluate("window.scrollBy(0, window.innerHeight)")
                        page.wait_for_timeout(600)

                    html = page.content()
                    stats["pages_fetched"] += 1

                    if http_status and http_status >= 400:
                        logger.warning("HTTP %s for %s — stopping pagination", http_status, url)
                        company_failed = True
                        break

                except PWTimeout:
                    logger.warning("Timeout fetching %s — stopping pagination", url)
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
                        scraper_version="insurance-scrape-1.0",
                        is_parsed=True,
                        scraped_at=datetime.now(timezone.utc),
                    ))

                # Extract reviews
                raw_reviews = _extract_trustpilot_reviews(html)
                page_review_count = len(raw_reviews)
                stats["reviews_found"] += page_review_count
                logger.info(
                    "Scraping %s page %d/%d — found %d reviews",
                    company_name, page_num, max_pages, page_review_count,
                )

                if not raw_reviews:
                    logger.info("No reviews on page %d — stopping pagination for %s", page_num, company_name)
                    break

                # Store reviews
                page_new = 0
                with get_db_session() as session:
                    for rev in raw_reviews[:25]:
                        text = (rev.get("review_text") or "").strip()
                        if not text or len(text) < 15:
                            continue

                        ch = _content_hash(url, text)
                        existing = session.query(InsuranceReview).filter(
                            InsuranceReview.content_hash == ch
                        ).first()
                        if existing:
                            stats["reviews_duplicate"] += 1
                            continue

                        try:
                            review = InsuranceReview(
                                company_id=company_id,
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

                company_total_new += page_new

                # Random delay between pages (4-8 seconds)
                if page_num < max_pages and raw_reviews:
                    delay = random.uniform(4, 8)
                    logger.info("Waiting %.1fs before next page...", delay)
                    time.sleep(delay)

            # End pagination for this company
            stats["companies_scraped"] += 1
            logger.info(
                "Inserted %d new reviews for %s (across %d pages)",
                company_total_new, company_name, max_pages,
            )

            if company_failed:
                logger.warning("Company %s had HTTP errors", company_name)

            # Polite delay between companies (3-5 seconds)
            delay = random.uniform(3, 5)
            logger.info("Waiting %.1fs before next company...", delay)
            time.sleep(delay)

        page.close()
        context.close()
        browser.close()

    # Record pipeline step run
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
    logger.info("Insurance Review Scrape Summary")
    logger.info("=" * 60)
    logger.info("Companies scraped:    %d", stats["companies_scraped"])
    logger.info("Companies skipped:    %d (freshness)", stats["companies_skipped_fresh"])
    logger.info("Pages fetched:        %d", stats["pages_fetched"])
    logger.info("Reviews found:        %d", stats["reviews_found"])
    logger.info("Reviews inserted:     %d", stats["reviews_inserted"])
    logger.info("Reviews duplicate:    %d", stats["reviews_duplicate"])
    logger.info("Reviews failed:       %d", stats["reviews_failed"])
    logger.info("=" * 60)

    return stats


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Scrape insurance company reviews from Trustpilot")
    ap.add_argument("--max-pages", type=int, default=5, help="Max pages per company")
    ap.add_argument("--freshness-hours", type=int, default=12,
                    help="Skip companies scraped within this many hours (0 = always scrape)")
    args = ap.parse_args()
    ingest_insurance_reviews(max_pages=args.max_pages, freshness_hours=args.freshness_hours)
