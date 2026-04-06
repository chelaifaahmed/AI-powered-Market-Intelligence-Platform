#!/usr/bin/env python3
"""
scripts/run_insurance_reviews_ingest.py
---------------------------------------
Ingests real consumer insurance company reviews from Trustpilot using Playwright.

Stores results in `insurance_reviews` with `data_origin='scraped'`.
Runs NLP pipeline on new reviews after each company.

Usage:
    python scripts/run_insurance_reviews_ingest.py [--max-pages 5] [--freshness-hours 12]
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
logger = logging.getLogger("scripts.insurance_reviews_ingest")

# ---------------------------------------------------------------------------
# Pagination config
# ---------------------------------------------------------------------------
MAX_PAGES = 5

# ---------------------------------------------------------------------------
# Source registry — Trustpilot insurance company pages
# (company_name, trustpilot_domain)
# ---------------------------------------------------------------------------
INSURANCE_SOURCES = [
    ("Admiral", "admiral.com"),
    ("Allianz", "allianz.co.uk"),
    ("AXA", "axa.co.uk"),
    ("Aviva", "aviva.co.uk"),
    ("Direct Line", "directline.com"),
    ("Hastings Direct", "hastingsdirect.com"),
    ("Churchill", "churchill.com"),
    ("LV=", "lv.com"),
    ("Generali", "generali.com"),
    ("Zurich Insurance", "zurich.co.uk"),
    ("RSA Insurance", "www.rsagroup.com"),
    ("Intact Insurance", "intact.ca"),
]


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


def _extract_trustpilot_reviews(html: str) -> list[dict]:
    """Extract review cards from Trustpilot page HTML."""
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
    """Parse one Trustpilot review card."""
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
    p_tags = card.find_all("p")
    for p in p_tags:
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
        dt_attr = time_el.get("datetime", "")
        review_date = _parse_iso_date(dt_attr)

    return {
        "review_title": title,
        "review_text": body,
        "rating": rating,
        "author": author,
        "review_date": review_date,
    }


def _get_company(session, company_name: str):
    """Find an InsuranceCompany by name (case-insensitive)."""
    from database.models import InsuranceCompany
    return session.query(InsuranceCompany).filter(
        InsuranceCompany.name.ilike(company_name)
    ).first()


def _get_trustpilot_source(session):
    """Get the Trustpilot ReviewSource row."""
    from database.models import ReviewSource
    return session.query(ReviewSource).filter(
        ReviewSource.name.ilike("%trustpilot%")
    ).first()


def _company_recently_scraped(session, company_name: str, hours: int = 12) -> bool:
    """Return True if we already have scraped reviews for this company within `hours`."""
    from database.models import InsuranceReview, InsuranceCompany
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    company = _get_company(session, company_name)
    if not company:
        return False
    recent = (
        session.query(InsuranceReview.id)
        .filter(
            InsuranceReview.company_id == company.id,
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


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------

def ingest_insurance_reviews(
    max_pages: int = 5,
    max_per_page: int = 25,
    freshness_hours: int = 12,
) -> dict:
    """Fetch and ingest real insurance company reviews from Trustpilot."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    from database.connection import get_db_session
    from database.models import InsuranceReview, RawPage
    from nlp.nlp_pipeline import NlpPipeline

    global MAX_PAGES
    MAX_PAGES = max_pages

    run_started = datetime.now(timezone.utc)
    stats = {
        "pages_fetched": 0,
        "reviews_found": 0,
        "reviews_inserted": 0,
        "reviews_duplicate": 0,
        "reviews_failed": 0,
        "companies_skipped_fresh": 0,
        "companies_not_found": 0,
        "nlp_processed": 0,
    }

    logger.info(
        "Starting insurance review ingestion — %d companies, up to %d pages each",
        len(INSURANCE_SOURCES), MAX_PAGES,
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

        for company_name, tp_domain in INSURANCE_SOURCES:
            # Check company exists in DB
            with get_db_session() as session:
                company = _get_company(session, company_name)
                if not company:
                    logger.warning("Company '%s' not found in DB — skipping", company_name)
                    stats["companies_not_found"] += 1
                    continue
                company_id = company.id

                # Freshness check
                if _company_recently_scraped(session, company_name, hours=freshness_hours):
                    logger.info("Skipping %s — scraped within last %dh", company_name, freshness_hours)
                    stats["companies_skipped_fresh"] += 1
                    continue

                # Get Trustpilot source ID
                tp_source = _get_trustpilot_source(session)
                source_id = tp_source.id if tp_source else None

            base_url = f"https://www.trustpilot.com/review/{tp_domain}"
            company_total_new = 0

            # ------ Paginate ------
            for page_num in range(1, MAX_PAGES + 1):
                url = f"{base_url}?page={page_num}"
                logger.info("Scraping %s page %d/%d — %s", company_name, page_num, MAX_PAGES, url)

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
                        ]:
                            try:
                                page.click(sel, timeout=2000)
                                break
                            except Exception:
                                pass

                    # Scroll
                    for _ in range(4):
                        page.evaluate("window.scrollBy(0, window.innerHeight)")
                        page.wait_for_timeout(600)

                    html = page.content()
                    stats["pages_fetched"] += 1

                    if http_status and http_status >= 400:
                        logger.warning("HTTP %s for %s — stopping", http_status, url)
                        break

                except PWTimeout:
                    logger.warning("Timeout fetching %s", url)
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
                        scraper_version="insurance-reviews-ingest-1.0",
                        is_parsed=True,
                        scraped_at=datetime.now(timezone.utc),
                    ))

                # Extract reviews
                raw_reviews = _extract_trustpilot_reviews(html)
                page_count = len(raw_reviews)
                stats["reviews_found"] += page_count
                logger.info("%s page %d — found %d reviews", company_name, page_num, page_count)

                if not raw_reviews:
                    logger.info("No reviews on page %d — stopping for %s", page_num, company_name)
                    break

                # Store reviews
                page_new = 0
                with get_db_session() as session:
                    for rev in raw_reviews[:max_per_page]:
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
                                source_id=source_id,
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

                # Rate limiting delay between pages
                if page_num < MAX_PAGES and raw_reviews:
                    delay = random.uniform(3, 7)
                    logger.info("Waiting %.1fs before next page...", delay)
                    time.sleep(delay)

            # End pagination for this company
            logger.info("Inserted %d new reviews for %s", company_total_new, company_name)

            # Run NLP on new insurance reviews
            if company_total_new > 0:
                logger.info("Running NLP on %d new insurance reviews...", company_total_new)
                try:
                    with get_db_session() as session:
                        nlp = NlpPipeline(session)
                        nlp_metrics = nlp.process_insurance_reviews(limit=company_total_new + 10)
                        stats["nlp_processed"] += nlp_metrics.get("records_processed", 0)
                        logger.info("NLP: %s", nlp_metrics)
                except Exception as exc:
                    logger.error("NLP failed: %s", exc)

            # Polite delay between companies
            time.sleep(3)

        page.close()
        context.close()
        browser.close()

    # Record step run
    from database.models import PipelineStepRun
    from database.enums import PipelineStatus
    run_status = "success" if stats["reviews_failed"] == 0 else (
        "partial" if stats["reviews_inserted"] > 0 else "failed"
    )
    try:
        with get_db_session() as session:
            finished = datetime.now(timezone.utc)
            duration_ms = int((finished - run_started).total_seconds() * 1000)
            step = PipelineStepRun(
                step_name="insurance_reviews_ingest_trustpilot",
                status=PipelineStatus(run_status),
                started_at=run_started,
                finished_at=finished,
                duration_ms=duration_ms,
                records_seen=stats["reviews_found"],
                records_processed=stats["reviews_inserted"],
                records_skipped=stats["reviews_duplicate"] + stats["companies_skipped_fresh"],
                records_failed=stats["reviews_failed"],
                records_inserted=stats["reviews_inserted"],
                error_count=stats["reviews_failed"],
                step_metadata={
                    "pages_fetched": stats["pages_fetched"],
                    "nlp_processed": stats["nlp_processed"],
                    "companies_not_found": stats["companies_not_found"],
                },
            )
            session.add(step)
        logger.info("Recorded PipelineStepRun (status=%s)", run_status)
    except Exception as exc:
        logger.warning("Could not record step run: %s", exc)

    # Summary
    logger.info("=" * 60)
    logger.info("Insurance Review Ingestion Summary")
    logger.info("=" * 60)
    logger.info("Pages fetched:       %d", stats["pages_fetched"])
    logger.info("Companies skipped:   %d (freshness)", stats["companies_skipped_fresh"])
    logger.info("Companies not found: %d", stats["companies_not_found"])
    logger.info("Reviews found:       %d", stats["reviews_found"])
    logger.info("Reviews inserted:    %d", stats["reviews_inserted"])
    logger.info("Reviews duplicate:   %d", stats["reviews_duplicate"])
    logger.info("Reviews failed:      %d", stats["reviews_failed"])
    logger.info("NLP processed:       %d", stats["nlp_processed"])
    logger.info("=" * 60)

    return stats


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Ingest real insurance reviews from Trustpilot")
    ap.add_argument("--max-pages", type=int, default=5, help="Max pages per company")
    ap.add_argument("--max-per-page", type=int, default=25, help="Max reviews per page")
    ap.add_argument("--freshness-hours", type=int, default=12,
                    help="Skip companies scraped within this many hours (0 = always scrape)")
    args = ap.parse_args()
    ingest_insurance_reviews(
        max_pages=args.max_pages,
        max_per_page=args.max_per_page,
        freshness_hours=args.freshness_hours,
    )
