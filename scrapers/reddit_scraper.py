"""
scrapers/reddit_scraper.py
---------------------------
Scrapes Reddit posts from insurance and automotive subreddits for brand
sentiment and market intelligence. Stores results as MarketTrendArticles.

SETUP (free, 2 minutes):
  1. Go to https://www.reddit.com/prefs/apps
  2. Click "create another app" → choose type: "script"
  3. Name: "TW-Intel" (any name works)
  4. Redirect URI: http://localhost  (required but unused for script apps)
  5. Click "create app"
  6. Copy:
       - client_id    = the string under the app name (looks like "abc123xyz")
       - client_secret = the "secret" field
  7. Add to .env:
       REDDIT_CLIENT_ID=abc123xyz
       REDDIT_CLIENT_SECRET=your_secret_here

No paid plan needed. The free "script" app tier gives 60 requests/minute.

Public API:
    run_reddit_scraper() -> dict
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger("scrapers.reddit")

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_API_BASE  = "https://oauth.reddit.com"
_USER_AGENT = "TW-Intel/1.0 (PFE Market Intelligence; contact: twteam@pfe.tn)"

# Subreddits + search queries for insurance
_INSURANCE_SEARCHES: List[Tuple[str, str]] = [
    ("Insurance",    "AXA review"),
    ("Insurance",    "Allianz review"),
    ("Insurance",    "Groupama review"),
    ("Insurance",    "Generali review"),
    ("CarInsurance", "best insurance"),
    ("CarInsurance", "worst insurance company"),
    ("Insurance",    "claim denied"),
    ("Insurance",    "insurance complaint"),
]

# Subreddits + search queries for automotive
_CAR_SEARCHES: List[Tuple[str, str]] = [
    ("cars",         "Toyota reliability"),
    ("cars",         "Hyundai problems"),
    ("cars",         "Volkswagen issues"),
    ("cars",         "Renault review"),
    ("cars",         "Kia experience"),
    ("whatcarshouldIbuy", "best car 2024"),
    ("MechanicAdvice",    "common problems"),
    ("cars",         "recall"),
]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _get_token(client_id: str, client_secret: str, timeout: int = 15) -> Optional[str]:
    """Exchange client credentials for a Bearer token."""
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    body = urlencode({"grant_type": "client_credentials"}).encode("utf-8")
    req = Request(
        _TOKEN_URL,
        data=body,
        headers={
            "Authorization": f"Basic {credentials}",
            "User-Agent": _USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            token = data.get("access_token")
            if not token:
                logger.error("Reddit auth failed: %s", data)
            return token
    except Exception as e:
        logger.error("Reddit token request failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def _search(token: str, subreddit: str, query: str, limit: int = 25, timeout: int = 15) -> List[Dict]:
    """Search a subreddit and return post data dicts."""
    params = urlencode({
        "q": query,
        "sort": "relevance",
        "t": "year",
        "limit": limit,
        "restrict_sr": "true",
    })
    url = f"{_API_BASE}/r/{subreddit}/search?{params}"
    req = Request(url, headers={
        "Authorization": f"bearer {token}",
        "User-Agent": _USER_AGENT,
        "Accept": "application/json",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            children = data.get("data", {}).get("children", [])
            return [c.get("data", {}) for c in children]
    except HTTPError as e:
        logger.warning("HTTP %s searching r/%s q=%r", e.code, subreddit, query)
    except Exception as e:
        logger.warning("Error searching r/%s q=%r: %s", subreddit, query, e)
    return []


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_or_create_source(session):
    from database.models import ReviewSource
    from database.enums import SourceType

    source = session.query(ReviewSource).filter_by(name="Reddit").first()
    if source:
        return source
    source = ReviewSource(
        name="Reddit",
        base_url="https://www.reddit.com",
        reliability_score=0.65,
        is_active=True,
        region="Global",
        source_type=SourceType.FORUM,
    )
    session.add(source)
    session.flush()
    logger.info("Created ReviewSource: Reddit")
    return source


def _infer_category(subreddit: str, query: str) -> str:
    s = subreddit.lower()
    q = query.lower()
    if "insurance" in s or "insurance" in q:
        return "Insurance"
    if "ev" in s or "electric" in q:
        return "EV"
    return "Automotive"


def _insert_post(session, post: Dict, source_id, category: str) -> bool:
    """Insert a Reddit post as a MarketTrendArticle. Returns True if inserted."""
    from database.models import MarketTrendArticle

    title = (post.get("title") or "").strip()
    text = (post.get("selftext") or "").strip()
    subreddit = post.get("subreddit") or ""
    permalink = f"https://reddit.com{post.get('permalink', '')}"

    if not title:
        return False

    # Use permalink as canonical URL (more stable than url which can be external)
    source_url = permalink

    # Dedup on source_url first
    exists = session.query(MarketTrendArticle).filter_by(source_url=source_url).first()
    if exists:
        return False

    # Also dedup on content_hash
    body = f"{title} {text}"[:500]
    content_hash = hashlib.sha256(f"reddit|{source_url}|{body}".encode()).hexdigest()
    exists = session.query(MarketTrendArticle).filter_by(content_hash=content_hash).first()
    if exists:
        return False

    # Parse date from epoch
    epoch = post.get("created_utc")
    pub_date = datetime.fromtimestamp(epoch, tz=timezone.utc).date() if epoch else None

    # Combine title + body for body_text; include subreddit context
    full_body = f"[r/{subreddit}] {text}" if text else None

    tags = [subreddit.lower()]

    from parsers.data_gateway import clean_article
    cleaned = clean_article({
        "title": title,
        "source_url": source_url,
        "body_text": full_body,
        "author": post.get("author"),
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
        region="Global",
        content_hash=content_hash,
        data_origin="scraped",
        is_processed=False,
        confidence_score=0.65,
    )
    session.add(record)
    try:
        session.flush()
        return True
    except Exception as e:
        session.rollback()
        logger.warning("Insert failed for Reddit post: %s", e)
        return False


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_reddit_scraper(
    include_insurance: bool = True,
    include_cars: bool = True,
) -> Dict:
    """
    Scrape Reddit posts about insurance and automotive brands.

    Requires REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env.
    Returns metrics dict.
    """
    import os, sys
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    client_id = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()

    if not client_id or not client_secret:
        logger.error(
            "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET not set. "
            "Register a free script app at https://www.reddit.com/prefs/apps "
            "and add both to .env"
        )
        return {"error": "Reddit credentials not configured", "inserted": 0}

    token = _get_token(client_id, client_secret)
    if not token:
        return {"error": "Reddit authentication failed", "inserted": 0}

    logger.info("Reddit auth OK — starting scrape")

    from database.connection import get_db_session

    metrics = {"fetched": 0, "inserted": 0, "duplicate": 0, "errors": 0}

    with get_db_session() as session:
        source = _get_or_create_source(session)

        searches = []
        if include_insurance:
            searches.extend(_INSURANCE_SEARCHES)
        if include_cars:
            searches.extend(_CAR_SEARCHES)

        for subreddit, query in searches:
            logger.info("Searching r/%s: %r", subreddit, query)
            posts = _search(token, subreddit, query)
            metrics["fetched"] += len(posts)

            category = _infer_category(subreddit, query)
            for post in posts:
                if _insert_post(session, post, source.id, category):
                    metrics["inserted"] += 1
                else:
                    metrics["duplicate"] += 1

            time.sleep(1.0)  # Reddit: 60 req/min limit

        source.total_records_scraped = (source.total_records_scraped or 0) + metrics["inserted"]
        source.last_scraped_at = datetime.now(timezone.utc)
        session.flush()

    logger.info("Reddit scrape done: fetched=%d inserted=%d", metrics["fetched"], metrics["inserted"])
    return metrics
