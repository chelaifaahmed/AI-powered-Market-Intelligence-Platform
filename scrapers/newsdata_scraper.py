"""
scrapers/newsdata_scraper.py
-----------------------------
Fetches news articles from newsdata.io for insurance and automotive topics.
Stores results as MarketTrendArticles (data_origin='scraped').

API docs: https://newsdata.io/documentation
Free tier: 200 credits/day, 10 articles per request.

SETUP:
  Add to .env:
      NEWSDATA_API_KEY=pub_517ec03477c1452bbb602be45585594b

Public API:
    run_newsdata_scraper() -> dict
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger("scrapers.newsdata")

_BASE_URL = "https://newsdata.io/api/1/news"
_USER_AGENT = "TW-Intel/1.0"

# ---------------------------------------------------------------------------
# Search queries — (query, our_category, region, language, country_filter)
# ---------------------------------------------------------------------------
# Insurance market — EU focus
_INSURANCE_QUERIES: List[Dict] = [
    {"q": "AXA insurance review",          "category": "Insurance", "region": "EU",     "language": "en"},
    {"q": "Allianz insurance claims",       "category": "Insurance", "region": "EU",     "language": "en"},
    {"q": "Groupama assurance",             "category": "Insurance", "region": "EU",     "language": "fr"},
    {"q": "Generali insurance market",      "category": "Insurance", "region": "EU",     "language": "en"},
    {"q": "insurance market Africa",        "category": "Insurance", "region": "TN",     "language": "en"},
    {"q": "assurance auto Tunisie",         "category": "Insurance", "region": "TN",     "language": "fr"},
    {"q": "assurance automobile Maroc",     "category": "Insurance", "region": "TN",     "language": "fr"},
    {"q": "insurance digital transformation", "category": "Insurance", "region": "Global", "language": "en"},
    {"q": "car insurance EV electric vehicle", "category": "Insurance", "region": "EU",  "language": "en"},
]

# Automotive market
_CAR_QUERIES: List[Dict] = [
    {"q": "Toyota recall 2024",             "category": "Automotive", "region": "Global", "language": "en"},
    {"q": "Hyundai electric car sales",     "category": "EV",         "region": "Global", "language": "en"},
    {"q": "Volkswagen market share Europe", "category": "Automotive", "region": "EU",     "language": "en"},
    {"q": "electric vehicle sales Europe",  "category": "EV",         "region": "EU",     "language": "en"},
    {"q": "car market Tunisia importation", "category": "Automotive", "region": "TN",     "language": "fr"},
    {"q": "automobile Tunisie 2024",        "category": "Automotive", "region": "TN",     "language": "fr"},
    {"q": "EV battery charging infrastructure", "category": "EV",    "region": "EU",     "language": "en"},
    {"q": "automotive leasing fleet management", "category": "Automotive", "region": "EU", "language": "en"},
    {"q": "car dealer digital transformation",  "category": "Technology", "region": "Global", "language": "en"},
    {"q": "véhicule électrique marché Europe",  "category": "EV",    "region": "EU",     "language": "fr"},
]


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _fetch_articles(api_key: str, query: str, language: str, timeout: int = 15) -> List[Dict]:
    """Call newsdata.io /news endpoint and return article list."""
    params = urlencode({
        "apikey": api_key,
        "q": query,
        "language": language,
    })
    url = f"{_BASE_URL}?{params}"
    req = Request(url, headers={
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") != "success":
                logger.warning("newsdata.io error for %r: %s", query, data.get("message") or data.get("results"))
                return []
            return data.get("results") or []
    except HTTPError as e:
        logger.warning("HTTP %s from newsdata.io for %r: %s", e.code, query, e.read()[:200])
    except URLError as e:
        logger.warning("URLError from newsdata.io for %r: %s", query, e.reason)
    except Exception as e:
        logger.warning("Error from newsdata.io for %r: %s", query, e)
    return []


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_or_create_source(session):
    from database.models import ReviewSource
    from database.enums import SourceType

    source = session.query(ReviewSource).filter_by(name="newsdata.io").first()
    if source:
        return source
    source = ReviewSource(
        name="newsdata.io",
        base_url="https://newsdata.io",
        reliability_score=0.80,
        is_active=True,
        region="Global",
        source_type=SourceType.NEWS_BLOG,
    )
    session.add(source)
    session.flush()
    logger.info("Created ReviewSource: newsdata.io")
    return source


def _parse_pub_date(raw: Optional[str]):
    """Parse newsdata.io pubDate format: '2024-01-15 10:32:00' or ISO."""
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(raw[:19], fmt[:len(raw[:19])]).date()
        except Exception:
            pass
    # Fallback: parse ISO
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except Exception:
        return None


def _insert_article(session, article: Dict, source_id, category: str, region: str) -> bool:
    """Insert a newsdata.io article as MarketTrendArticle. Returns True if inserted."""
    from database.models import MarketTrendArticle

    title = (article.get("title") or "").strip()
    source_url = (article.get("link") or "").strip()

    if not title or not source_url or title == "[Removed]":
        return False

    # Dedup on URL
    if session.query(MarketTrendArticle).filter_by(source_url=source_url).first():
        return False

    content_hash = hashlib.sha256(f"newsdata|{source_url}|{title}".encode()).hexdigest()
    if session.query(MarketTrendArticle).filter_by(content_hash=content_hash).first():
        return False

    # Body text: prefer description, fall back to content (may be truncated on free tier)
    description = (article.get("description") or "").strip()
    content = (article.get("content") or "").strip()
    body_raw = description or content or ""
    source_name = article.get("source_id") or ""
    body_text = (f"[{source_name}] {body_raw}" if source_name and body_raw else body_raw) or None

    # Author
    creators = article.get("creator") or []
    author: Optional[str] = creators[0].strip() if creators else None

    # Tags: from newsdata categories + source
    nd_cats = article.get("category") or []
    tags = [c.lower() for c in nd_cats if c] + ([source_name.lower()] if source_name else [])

    pub_date = _parse_pub_date(article.get("pubDate"))

    from parsers.data_gateway import clean_article
    cleaned = clean_article({
        "title": title,
        "source_url": source_url,
        "body_text": body_text,
        "author": author,
        "publication_date": pub_date,
    })
    if cleaned is None:
        return False

    record = MarketTrendArticle(
        source_id=source_id,
        title=cleaned["title"],
        source_url=cleaned["source_url"],
        author=cleaned["author"],
        publication_date=cleaned["publication_date"],
        body_text=cleaned["body_text"],
        tags=tags,
        category=category,
        region=region,
        content_hash=content_hash,
        data_origin="scraped",
        is_processed=False,
        confidence_score=0.80,
    )
    session.add(record)
    try:
        session.flush()
        return True
    except Exception as e:
        session.rollback()
        logger.warning("Insert failed for newsdata article %r: %s", title[:60], e)
        return False


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_newsdata_scraper(
    include_insurance: bool = True,
    include_cars: bool = True,
) -> Dict:
    """
    Fetch recent news articles from newsdata.io for insurance and automotive topics.

    Requires NEWSDATA_API_KEY in environment (.env).
    Free tier: 200 credits/day, 10 results per request.
    Returns metrics dict.
    """
    import os
    import sys
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    from dotenv import load_dotenv
    load_dotenv(os.path.join(_root, ".env"))

    api_key = os.environ.get("NEWSDATA_API_KEY", "").strip()
    if not api_key:
        logger.error(
            "NEWSDATA_API_KEY not set. "
            "Get your key at https://newsdata.io and add to .env: "
            "NEWSDATA_API_KEY=pub_..."
        )
        return {"error": "NEWSDATA_API_KEY not configured", "inserted": 0}

    from database.connection import get_db_session

    metrics: Dict = {"fetched": 0, "inserted": 0, "duplicate": 0, "errors": 0}

    queries: List[Dict] = []
    if include_insurance:
        queries.extend(_INSURANCE_QUERIES)
    if include_cars:
        queries.extend(_CAR_QUERIES)

    with get_db_session() as session:
        source = _get_or_create_source(session)

        for cfg in queries:
            q = cfg["q"]
            category = cfg["category"]
            region = cfg["region"]
            language = cfg.get("language", "en")

            logger.info("newsdata.io search: %r (lang=%s)", q, language)
            articles = _fetch_articles(api_key, q, language)
            metrics["fetched"] += len(articles)

            for article in articles:
                if _insert_article(session, article, source.id, category, region):
                    metrics["inserted"] += 1
                else:
                    metrics["duplicate"] += 1

            # Stay well under 200 credits/day — pause between queries
            time.sleep(1.0)

        source.total_records_scraped = (source.total_records_scraped or 0) + metrics["inserted"]
        source.last_scraped_at = datetime.now(timezone.utc)
        session.flush()

    logger.info(
        "newsdata.io scrape done: fetched=%d inserted=%d duplicate=%d errors=%d",
        metrics["fetched"], metrics["inserted"], metrics["duplicate"], metrics["errors"],
    )
    return metrics
