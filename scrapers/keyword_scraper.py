"""
scrapers/keyword_scraper.py
----------------------------
Searches for articles matching user-defined keywords via public RSS search feeds.

Sources:
  - Google News RSS: https://news.google.com/rss/search?q={keyword}&hl=en
  - Bing News RSS:   https://www.bing.com/news/search?q={keyword}&format=rss

Articles are stored in market_trend_articles with data_origin='scraped' and
the keyword tagged in the 'tags' column.
"""

from __future__ import annotations

import hashlib
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logger = logging.getLogger("scrapers.keyword_scraper")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
}


def _fetch_rss(url: str, timeout: int = 15) -> Optional[bytes]:
    """Fetch RSS feed bytes from URL."""
    req = Request(url, headers={
        "User-Agent": _USER_AGENT,
        "Accept": "application/rss+xml,application/xml,text/xml,*/*",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            logger.info("Fetched %s — %d bytes", url, len(content))
            return content
    except HTTPError as e:
        logger.warning("HTTP %s fetching %s", e.code, url)
    except URLError as e:
        logger.warning("URLError fetching %s: %s", url, e.reason)
    except Exception as e:
        logger.warning("Failed fetching %s: %s", url, e)
    return None


def _text(el: Optional[ET.Element]) -> Optional[str]:
    if el is None:
        return None
    return (el.text or "").strip() or None


def _parse_date(raw: Optional[str]):
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


def _parse_rss_items(xml_bytes: bytes) -> List[Dict]:
    """Parse RSS items from XML bytes."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logger.warning("XML parse error: %s", e)
        return []

    items = []
    tag = root.tag.lower()

    # Atom feed
    if "feed" in tag:
        entries = (
            root.findall("atom:entry", _NS)
            or root.findall("{http://www.w3.org/2005/Atom}entry")
            or root.findall("entry")
        )
        for entry in entries:
            link_el = (
                entry.find("atom:link", _NS)
                or entry.find("{http://www.w3.org/2005/Atom}link")
                or entry.find("link")
            )
            link = link_el.get("href") if link_el is not None else _text(entry.find("link"))
            title_el = (
                entry.find("atom:title", _NS)
                or entry.find("{http://www.w3.org/2005/Atom}title")
                or entry.find("title")
            )
            title = _text(title_el)
            pub_el = (
                entry.find("atom:published", _NS)
                or entry.find("{http://www.w3.org/2005/Atom}published")
                or entry.find("published")
            )
            pub_date = _parse_date(_text(pub_el))
            if title and link:
                items.append({"title": title, "link": link, "pub_date": pub_date})
        return items

    # RSS 2.0
    channel = root.find("channel")
    entries = channel.findall("item") if channel is not None else root.findall("item")

    for item in entries:
        title = _text(item.find("title"))
        link = _text(item.find("link"))
        if not link:
            guid = _text(item.find("guid"))
            if guid and guid.startswith("http"):
                link = guid
        pub_date = _parse_date(_text(item.find("pubDate")))
        body = _text(item.find("description"))
        if title and link:
            items.append({"title": title, "link": link, "pub_date": pub_date, "body": body})

    return items


def search_keyword(keyword: str, region: Optional[str] = None) -> List[Dict]:
    """Search for articles matching keyword via Google News + Bing News RSS.

    Returns list of article dicts: {title, link, pub_date, source_feed, body}.
    """
    encoded = quote_plus(keyword)
    hl = "en"
    if region:
        region_map = {"TN": "fr", "EU": "en", "US": "en"}
        hl = region_map.get(region, "en")

    feeds = [
        (f"https://news.google.com/rss/search?q={encoded}&hl={hl}", "Google News"),
        (f"https://www.bing.com/news/search?q={encoded}&format=rss", "Bing News"),
    ]

    all_articles: List[Dict] = []

    for feed_url, source_name in feeds:
        xml_bytes = _fetch_rss(feed_url)
        if not xml_bytes:
            continue

        items = _parse_rss_items(xml_bytes)
        for item in items:
            item["source_feed"] = source_name
        all_articles.extend(items)

        logger.info("  %s: %d items for '%s'", source_name, len(items), keyword)
        time.sleep(1)

    return all_articles


def run_keyword_search(max_articles_per_keyword: int = 15) -> Dict:
    """Search all active keywords and store results as MarketTrendArticles.

    Returns metrics dict.
    """
    import os
    import sys
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)

    from database.connection import get_db_session
    from database.models import SearchKeyword, MarketTrendArticle, ReviewSource

    metrics = {
        "keywords_searched": 0,
        "articles_found": 0,
        "articles_inserted": 0,
        "articles_duplicate": 0,
    }

    with get_db_session() as session:
        keywords = session.query(SearchKeyword).filter(
            SearchKeyword.is_active.is_(True)
        ).all()

        if not keywords:
            logger.info("No active keywords to search")
            return metrics

        # Get or create a source for keyword searches
        source = session.query(ReviewSource).filter_by(name="Keyword Search").first()
        if not source:
            source = ReviewSource(
                name="Keyword Search",
                base_url="https://news.google.com",
                reliability_score=0.70,
                is_active=True,
                region="Global",
            )
            session.add(source)
            session.flush()

        for kw in keywords:
            logger.info("Searching keyword: '%s' (region=%s)", kw.keyword, kw.region)
            metrics["keywords_searched"] += 1

            articles = search_keyword(kw.keyword, kw.region)
            metrics["articles_found"] += len(articles)
            inserted = 0

            for art in articles[:max_articles_per_keyword]:
                title = (art.get("title") or "")[:500]
                link = art.get("link") or ""
                if not title or not link:
                    continue

                content_hash = hashlib.sha256(f"{link}|{title}".encode()).hexdigest()

                # Check for duplicate
                exists = session.query(MarketTrendArticle).filter(
                    (MarketTrendArticle.source_url == link)
                    | (MarketTrendArticle.content_hash == content_hash)
                ).first()

                if exists:
                    metrics["articles_duplicate"] += 1
                    continue

                body = art.get("body") or title

                article = MarketTrendArticle(
                    source_id=source.id,
                    title=title,
                    source_url=link,
                    publication_date=art.get("pub_date"),
                    body_text=body,
                    category="Keyword Search",
                    region=kw.region or "Global",
                    content_hash=content_hash,
                    is_processed=False,
                    data_origin="scraped",
                    tags=[kw.keyword, art.get("source_feed", "RSS")],
                )
                session.add(article)
                try:
                    session.flush()
                    inserted += 1
                    metrics["articles_inserted"] += 1
                except Exception as e:
                    session.rollback()
                    logger.warning("Failed inserting article '%s': %s", title[:60], e)

            # Update keyword metadata
            kw.last_searched_at = datetime.now(timezone.utc)
            kw.results_count = (kw.results_count or 0) + inserted
            session.flush()

            logger.info("  Keyword '%s': found=%d, inserted=%d", kw.keyword, len(articles), inserted)

            # Rate limiting between keywords
            time.sleep(2)

    logger.info("Keyword search complete: %s", metrics)
    return metrics
