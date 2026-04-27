"""
scrapers/atlas_magazine_scraper.py
------------------------------------
RSS scraper for Atlas Magazine (atlas-mag.net) — MENA insurance & reinsurance
industry news in French.

Feed URL: https://www.atlas-mag.net/rss.xml  (10 items, refreshes on publish)

Target model: MarketTrendArticle
Data origin:  scraped
Region:       TN (primary audience is North Africa / MENA insurance market)

Public API:
    run_atlas_magazine_scraper() -> dict  (metrics)
"""

from __future__ import annotations

import hashlib
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logger = logging.getLogger("scrapers.atlas_magazine")

_FEED_URL = "https://www.atlas-mag.net/rss.xml"
_SOURCE_NAME = "Atlas Magazine"
_SOURCE_URL = "https://www.atlas-mag.net"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

_DC_NS = "http://purl.org/dc/elements/1.1/"


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

def _fetch(url: str, timeout: int = 15) -> Optional[bytes]:
    req = Request(url, headers={
        "User-Agent": _USER_AGENT,
        "Accept": "application/rss+xml,application/xml,text/xml,*/*",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            logger.info("Fetched %s — %d bytes", url, len(data))
            return data
    except HTTPError as e:
        logger.warning("HTTP %s fetching %s", e.code, url)
    except URLError as e:
        logger.warning("URLError fetching %s: %s", url, e.reason)
    except Exception as e:
        logger.warning("Failed fetching %s: %s", url, e)
    return None


# ---------------------------------------------------------------------------
# RSS parsing
# ---------------------------------------------------------------------------

def _parse_date(raw: Optional[str]) -> Optional[object]:
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).date()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except Exception:
        pass
    return None


def _parse_feed(xml_bytes: bytes) -> List[Dict]:
    """Parse RSS 2.0 feed from Atlas Magazine, return list of article dicts."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logger.warning("XML parse error: %s", e)
        return []

    channel = root.find("channel")
    items_el = channel.findall("item") if channel is not None else root.findall("item")

    articles = []
    for item in items_el:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not link:
            guid = item.findtext("guid") or ""
            if guid.startswith("http"):
                link = guid.strip()
        pub_date = _parse_date(item.findtext("pubDate"))
        creator_el = item.find(f"{{{_DC_NS}}}creator")
        author = (creator_el.text or "").strip() if creator_el is not None else None

        if title and link:
            articles.append({
                "title": title,
                "link": link,
                "pub_date": pub_date,
                "author": author,
            })

    logger.info("Parsed %d items from Atlas Magazine feed", len(articles))
    return articles


# ---------------------------------------------------------------------------
# Main runner — writes directly to MarketTrendArticle
# ---------------------------------------------------------------------------

def run_atlas_magazine_scraper() -> Dict:
    """Fetch Atlas Magazine RSS and persist new articles to MarketTrendArticle.

    Returns metrics dict: {fetched, inserted, duplicate, errors}.
    """
    import os, sys
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    from database.connection import get_db_session
    from database.models import MarketTrendArticle, ReviewSource

    metrics = {"fetched": 0, "inserted": 0, "duplicate": 0, "errors": 0}

    xml_bytes = _fetch(_FEED_URL)
    if not xml_bytes:
        logger.error("Failed to fetch Atlas Magazine RSS feed")
        metrics["errors"] += 1
        return metrics

    articles = _parse_feed(xml_bytes)
    metrics["fetched"] = len(articles)

    if not articles:
        return metrics

    with get_db_session() as session:
        # Resolve source record
        source = session.query(ReviewSource).filter_by(name=_SOURCE_NAME).first()
        if not source:
            from database.enums import SourceType
            source = ReviewSource(
                name=_SOURCE_NAME,
                base_url=_SOURCE_URL,
                reliability_score=0.85,
                is_active=True,
                region="TN",
                source_type=SourceType.NEWS_BLOG,
            )
            session.add(source)
            session.flush()
            logger.info("Created new ReviewSource: %s", _SOURCE_NAME)

        for art in articles:
            title = art["title"][:500]
            link = art["link"]
            content_hash = hashlib.sha256(f"{link}|{title}".encode()).hexdigest()

            # Deduplicate
            exists = session.query(MarketTrendArticle).filter(
                (MarketTrendArticle.source_url == link)
                | (MarketTrendArticle.content_hash == content_hash)
            ).first()
            if exists:
                metrics["duplicate"] += 1
                continue

            article = MarketTrendArticle(
                source_id=source.id,
                title=title,
                source_url=link,
                publication_date=art["pub_date"],
                author=art.get("author"),
                body_text=title,          # RSS description is HTML noise; title is cleaner
                category="insurance",
                region="TN",
                content_hash=content_hash,
                is_processed=False,
                data_origin="scraped",
                tags=["atlas-magazine", "insurance", "MENA", "reinsurance"],
            )
            session.add(article)
            try:
                session.flush()
                metrics["inserted"] += 1
                logger.info("Inserted: %s", title[:80])
            except Exception as e:
                session.rollback()
                metrics["errors"] += 1
                logger.warning("Failed inserting '%s': %s", title[:60], e)

        # Update source metadata
        source.total_records_scraped = (source.total_records_scraped or 0) + metrics["inserted"]
        source.last_scraped_at = datetime.now(timezone.utc)
        session.flush()

    logger.info("Atlas Magazine scrape complete: %s", metrics)
    return metrics
