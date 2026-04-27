"""
scrapers/newsapi_scraper.py
----------------------------
Fetches news articles from NewsAPI.org for insurance and automotive topics.
Stores results as MarketTrendArticles.

SETUP (free, 1 minute):
  1. Go to https://newsapi.org/register
  2. Create a free account (no credit card needed)
  3. Copy your API key from the dashboard
  4. Add to .env:
       NEWS_API_KEY=your_key_here

Free tier limits:
  - 100 requests/day
  - Articles up to 1 month old
  - Developer use only (not commercial)

Public API:
    run_newsapi_scraper() -> dict
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger("scrapers.newsapi")

_BASE_URL = "https://newsapi.org/v2/everything"
_USER_AGENT = "TW-Intel/1.0"

# Search queries for insurance market intelligence
_INSURANCE_QUERIES: List[Dict] = [
    {"q": "AXA insurance review",       "category": "Insurance", "region": "EU"},
    {"q": "Allianz insurance claims",   "category": "Insurance", "region": "EU"},
    {"q": "Groupama assurance",         "category": "Insurance", "region": "EU"},
    {"q": "Generali insurance market",  "category": "Insurance", "region": "EU"},
    {"q": "insurance Tunisia Morocco",  "category": "Insurance", "region": "TN"},
    {"q": "assurance auto Tunisie",     "category": "Insurance", "region": "TN"},
    {"q": "insurance market Africa",    "category": "Insurance", "region": "TN"},
]

# Search queries for automotive market intelligence
_CAR_QUERIES: List[Dict] = [
    {"q": "Toyota recall 2024",         "category": "Automotive", "region": "Global"},
    {"q": "Hyundai electric car",       "category": "EV",         "region": "Global"},
    {"q": "Volkswagen market share",    "category": "Automotive", "region": "EU"},
    {"q": "electric vehicle insurance", "category": "Insurance",  "region": "EU"},
    {"q": "car market Tunisia",         "category": "Automotive", "region": "TN"},
    {"q": "automobile marché Tunisie",  "category": "Automotive", "region": "TN"},
    {"q": "EV sales Europe 2024",       "category": "EV",         "region": "EU"},
]


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _search_articles(api_key: str, query: str, language: str = "en",
                     page_size: int = 20, timeout: int = 15) -> List[Dict]:
    """Search NewsAPI.org and return article dicts."""
    # Free tier: only last 30 days
    from_date = (datetime.now() - timedelta(days=29)).strftime("%Y-%m-%d")

    params = urlencode({
        "q": query,
        "language": language,
        "sortBy": "relevancy",
        "pageSize": page_size,
        "from": from_date,
        "apiKey": api_key,
    })
    url = f"{_BASE_URL}?{params}"
    req = Request(url, headers={
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") != "ok":
                logger.warning("NewsAPI error for %r: %s", query, data.get("message"))
                return []
            return data.get("articles", [])
    except HTTPError as e:
        logger.warning("HTTP %s from NewsAPI for %r", e.code, query)
    except URLError as e:
        logger.warning("URLError from NewsAPI for %r: %s", query, e.reason)
    except Exception as e:
        logger.warning("Error from NewsAPI for %r: %s", query, e)
    return []


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_or_create_source(session):
    from database.models import ReviewSource
    from database.enums import SourceType

    source = session.query(ReviewSource).filter_by(name="NewsAPI").first()
    if source:
        return source
    source = ReviewSource(
        name="NewsAPI",
        base_url="https://newsapi.org",
        reliability_score=0.80,
        is_active=True,
        region="Global",
        source_type=SourceType.NEWS_BLOG,
    )
    session.add(source)
    session.flush()
    logger.info("Created ReviewSource: NewsAPI")
    return source


def _insert_article(session, article: Dict, source_id, category: str, region: str) -> bool:
    """Insert a NewsAPI article as a MarketTrendArticle. Returns True if inserted."""
    from database.models import MarketTrendArticle

    title = (article.get("title") or "").strip()
    source_url = (article.get("url") or "").strip()
    description = (article.get("description") or "").strip()
    content = (article.get("content") or "").strip()

    if not title or not source_url or title == "[Removed]":
        return False

    # Dedup on source_url
    exists = session.query(MarketTrendArticle).filter_by(source_url=source_url).first()
    if exists:
        return False

    body = description or content or ""
    content_hash = hashlib.sha256(f"newsapi|{source_url}|{title}".encode()).hexdigest()
    exists = session.query(MarketTrendArticle).filter_by(content_hash=content_hash).first()
    if exists:
        return False

    # Parse date
    pub_date = None
    raw_date = article.get("publishedAt")
    if raw_date:
        try:
            pub_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).date()
        except Exception:
            pass

    author = (article.get("author") or "").strip() or None
    source_name = (article.get("source") or {}).get("name")
    tags = [source_name.lower()] if source_name else []

    body_text = (f"[{source_name}] {body}" if source_name and body else body) or None

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
        logger.warning("Insert failed for NewsAPI article: %s", e)
        return False


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_newsapi_scraper(
    include_insurance: bool = True,
    include_cars: bool = True,
) -> Dict:
    """
    Fetch recent news articles from NewsAPI.org for insurance and automotive topics.

    Requires NEWS_API_KEY in environment (.env).
    Returns metrics dict.
    """
    import os, sys
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    api_key = os.environ.get("NEWS_API_KEY", "").strip()
    if not api_key:
        logger.error(
            "NEWS_API_KEY not set. "
            "Register free at https://newsapi.org/register and add to .env: "
            "NEWS_API_KEY=your_key_here"
        )
        return {"error": "NEWS_API_KEY not configured", "inserted": 0}

    from database.connection import get_db_session

    metrics = {"fetched": 0, "inserted": 0, "duplicate": 0, "errors": 0}

    with get_db_session() as session:
        source = _get_or_create_source(session)

        queries = []
        if include_insurance:
            queries.extend(_INSURANCE_QUERIES)
        if include_cars:
            queries.extend(_CAR_QUERIES)

        for config in queries:
            q = config["q"]
            category = config["category"]
            region = config["region"]

            # NewsAPI free tier: try English first, then French for TN queries
            languages = ["en"]
            if region == "TN" or "Tunisie" in q or "assurance" in q:
                languages = ["fr", "en"]

            for lang in languages:
                logger.info("NewsAPI search: %r (lang=%s)", q, lang)
                articles = _search_articles(api_key, q, language=lang)
                metrics["fetched"] += len(articles)

                for article in articles:
                    if _insert_article(session, article, source.id, category, region):
                        metrics["inserted"] += 1
                    else:
                        metrics["duplicate"] += 1

                time.sleep(0.5)  # stay well under 100 req/day

        source.total_records_scraped = (source.total_records_scraped or 0) + metrics["inserted"]
        source.last_scraped_at = datetime.now(timezone.utc)
        session.flush()

    logger.info("NewsAPI scrape done: fetched=%d inserted=%d", metrics["fetched"], metrics["inserted"])
    return metrics
