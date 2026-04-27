"""
scrapers/trustpilot_insurance_scraper.py
-----------------------------------------
Direct HTTP scraper for insurance company reviews on Trustpilot.
Uses the same __NEXT_DATA__ JSON extraction that powers the car review scraper.

Targets EU insurers with significant Trustpilot presence, prioritising those
with Tunisia operations (Groupama, AXA, Allianz, Generali).

Public API:
    run_trustpilot_insurance_scraper(pages_per_company=5) -> dict
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("scrapers.trustpilot_insurance")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# (display_name_in_db, trustpilot_slug, pages_to_scrape)
# Ordered by TN relevance: Groupama TN is a real subsidiary, AXA/Allianz operate in MENA
_TARGETS: List[Tuple[str, str, int]] = [
    ("Groupama",  "groupama.fr",         5),   # 1,265 reviews — top priority
    ("AXA",       "axa.com",             3),   # 163 reviews
    ("Allianz",   "allianz.com",         2),   # 60 reviews
    ("Generali",  "generali.com",        2),   # 31 reviews
    ("Munich Re", "munichre.com",        1),   # 9 reviews
]

_BASE_URL = "https://www.trustpilot.com/review/{slug}?languages=all&page={page}"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _fetch_page(slug: str, page: int, timeout: int = 15) -> Optional[str]:
    url = _BASE_URL.format(slug=slug, page=page)
    req = Request(url, headers={
        "User-Agent": _USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,*/*",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        logger.warning("HTTP %s fetching %s page %d", e.code, slug, page)
    except URLError as e:
        logger.warning("URLError fetching %s page %d: %s", slug, page, e.reason)
    except Exception as e:
        logger.warning("Error fetching %s page %d: %s", slug, page, e)
    return None


def _extract_reviews(html: str) -> List[Dict]:
    """Pull review list from Trustpilot's __NEXT_DATA__ JSON blob."""
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html, re.DOTALL,
    )
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        return data.get("props", {}).get("pageProps", {}).get("reviews", [])
    except (json.JSONDecodeError, AttributeError):
        return []


def _parse_review(raw: Dict) -> Optional[Dict]:
    """Normalise a single Trustpilot review dict."""
    text = (raw.get("text") or "").strip()
    if not text:
        return None

    rating = raw.get("rating")
    title = (raw.get("title") or "").strip()
    consumer = raw.get("consumer") or {}
    author = (consumer.get("displayName") or "").strip() or None
    is_verified = bool((raw.get("labels") or {}).get("verification", {}).get("isVerified"))

    pub_raw = (raw.get("dates") or {}).get("publishedDate")
    review_date = None
    if pub_raw:
        try:
            review_date = datetime.fromisoformat(pub_raw.replace("Z", "+00:00")).date()
        except Exception:
            pass

    return {
        "text": text[:2000],
        "title": title[:300] or None,
        "rating": float(rating) if rating is not None else None,
        "author": author,
        "review_date": review_date,
        "is_verified": is_verified,
        "language": raw.get("language"),
    }


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_or_create_company(session, name: str):
    """Find InsuranceCompany by name (case-insensitive prefix match)."""
    from database.models import InsuranceCompany
    from sqlalchemy import func

    company = (
        session.query(InsuranceCompany)
        .filter(func.lower(InsuranceCompany.name).contains(name.lower().split()[0]))
        .first()
    )
    if company:
        return company

    # Create minimal record
    company = InsuranceCompany(
        name=name,
        country="EU",
        region="EU",
        is_active=True,
    )
    session.add(company)
    session.flush()
    logger.info("Created InsuranceCompany: %s", name)
    return company


def _insert_review(session, review: Dict, company_id, source_id, slug: str, page: int) -> bool:
    """Insert one review; returns True if inserted, False if duplicate."""
    from database.models import InsuranceReview

    content_hash = hashlib.sha256(
        f"tp|{company_id}|{review['author']}|{review['text'][:80]}".encode()
    ).hexdigest()

    exists = session.query(InsuranceReview).filter_by(content_hash=content_hash).first()
    if exists:
        return False

    from parsers.data_gateway import clean_insurance_review
    cleaned = clean_insurance_review({
        "review_text": review["text"],
        "review_title": review["title"],
        "source_url": f"https://www.trustpilot.com/review/{slug}?page={page}",
        "rating": review["rating"],
        "author": review["author"],
        "review_date": review["review_date"],
    })
    if cleaned is None:
        return False

    record = InsuranceReview(
        company_id=company_id,
        source_id=source_id,
        source_url=cleaned["source_url"],
        rating=cleaned["rating"],
        review_title=cleaned["review_title"],
        review_text=cleaned["review_text"],
        author=cleaned["author"],
        review_date=cleaned["review_date"],
        is_verified=review["is_verified"],
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
        logger.warning("Insert failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_trustpilot_insurance_scraper(pages_per_company: int = 5) -> Dict:
    """
    Scrape Trustpilot reviews for EU insurance companies.
    Returns metrics dict: {fetched, inserted, duplicate, errors, by_company}
    """
    import os, sys
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    from database.connection import get_db_session
    from database.models import ReviewSource
    from database.enums import SourceType

    metrics: Dict = {"fetched": 0, "inserted": 0, "duplicate": 0, "errors": 0, "by_company": {}}

    with get_db_session() as session:
        source = session.query(ReviewSource).filter_by(name="Trustpilot").first()
        if not source:
            source = ReviewSource(
                name="Trustpilot",
                base_url="https://www.trustpilot.com",
                reliability_score=0.82,
                is_active=True,
                region="Global",
                source_type=SourceType.REVIEW_PLATFORM,
            )
            session.add(source)
            session.flush()

        for display_name, slug, default_pages in _TARGETS:
            pages = min(pages_per_company, default_pages)
            company = _get_or_create_company(session, display_name)
            comp_metrics = {"inserted": 0, "duplicate": 0, "errors": 0}

            for page in range(1, pages + 1):
                logger.info("[%s] Fetching page %d/%d", display_name, page, pages)
                html = _fetch_page(slug, page)
                if not html:
                    comp_metrics["errors"] += 1
                    break

                raw_reviews = _extract_reviews(html)
                if not raw_reviews:
                    logger.info("[%s] No reviews on page %d — stopping", display_name, page)
                    break

                metrics["fetched"] += len(raw_reviews)
                page_inserted = 0

                for raw in raw_reviews:
                    parsed = _parse_review(raw)
                    if not parsed:
                        continue
                    if _insert_review(session, parsed, company.id, source.id, slug, page):
                        comp_metrics["inserted"] += 1
                        metrics["inserted"] += 1
                        page_inserted += 1
                    else:
                        comp_metrics["duplicate"] += 1
                        metrics["duplicate"] += 1

                # Stop when a page (after the first) yields nothing new —
                # means we've caught up with previously scraped content
                if page_inserted == 0 and page > 1:
                    logger.info("[%s] No new reviews on page %d — stopping", display_name, page)
                    break

                time.sleep(2.5)  # Trustpilot rate limiting

            metrics["by_company"][display_name] = comp_metrics
            logger.info("[%s] Done: %s", display_name, comp_metrics)

            source.total_records_scraped = (source.total_records_scraped or 0) + comp_metrics["inserted"]
            source.last_scraped_at = datetime.now(timezone.utc)
            session.flush()

            time.sleep(1.5)  # pause between companies

    logger.info("Trustpilot insurance scrape complete: inserted=%d duplicate=%d", metrics["inserted"], metrics["duplicate"])
    return metrics
