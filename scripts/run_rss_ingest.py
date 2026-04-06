"""
scripts/run_rss_ingest.py
--------------------------
Real article ingestion from open RSS/Atom feeds.

Full end-to-end path:
    HTTP fetch → raw XML stored in raw_pages
    → parsed article fields extracted from RSS items
    → MarketTrendArticle rows inserted with data_origin='scraped'
    → NLP run immediately on new rows

Feeds targeted (no JS required, no auth, open access):
    - Autoblog          https://www.autoblog.com/rss.xml
    - InsideEVs         https://insideevs.com/feed/
    - Motor1            https://www.motor1.com/rss/news/all/
    - Electrek          https://electrek.co/feed/
    - AutoExpress       https://www.autoexpress.co.uk/rss
    - Car and Driver    https://www.caranddriver.com/rss/all.xml

Usage:
    python scripts/run_rss_ingest.py
    python scripts/run_rss_ingest.py --max-per-feed 15
    python scripts/run_rss_ingest.py --feeds autoblog insideevs
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("scripts.rss_ingest")

# ---------------------------------------------------------------------------
# Feed registry — open, non-paywalled, non-JS-rendered RSS/Atom feeds
# ---------------------------------------------------------------------------
FEEDS: Dict[str, Dict] = {
    "autoblog": {
        "url": "https://www.autoblog.com/rss.xml",
        "name": "Autoblog",
        "base_url": "https://www.autoblog.com",
        "category": "Market",
        "region": "Global",
        "reliability_score": 0.88,
    },
    "insideevs": {
        "url": "https://insideevs.com/feed/",
        "name": "InsideEVs",
        "base_url": "https://insideevs.com",
        "category": "EV",
        "region": "Global",
        "reliability_score": 0.87,
    },
    "motor1": {
        "url": "https://www.motor1.com/rss/news/all/",
        "name": "Motor1",
        "base_url": "https://www.motor1.com",
        "category": "Market",
        "region": "Global",
        "reliability_score": 0.85,
    },
    "electrek": {
        "url": "https://electrek.co/feed/",
        "name": "Electrek",
        "base_url": "https://electrek.co",
        "category": "EV",
        "region": "Global",
        "reliability_score": 0.85,
    },
    "autoexpress": {
        "url": "https://www.autoexpress.co.uk/rss",
        "name": "Auto Express",
        "base_url": "https://www.autoexpress.co.uk",
        "category": "Market",
        "region": "Europe",
        "reliability_score": 0.90,
    },
    "caranddriver": {
        "url": "https://www.caranddriver.com/rss/all.xml",
        "name": "Car and Driver",
        "base_url": "https://www.caranddriver.com",
        "category": "Technology",
        "region": "North America",
        "reliability_score": 0.96,
    },
    # Tunisia-specific feeds (business/tech news with automotive relevance)
    "webmanagercenter": {
        "url": "https://www.webmanagercenter.com/feed/",
        "name": "Web Manager Center",
        "base_url": "https://www.webmanagercenter.com",
        "category": "Market",
        "region": "TN",
        "reliability_score": 0.75,
    },
    "businessnews_tn": {
        "url": "https://www.businessnews.com.tn/rss",
        "name": "Business News TN",
        "base_url": "https://www.businessnews.com.tn",
        "category": "Market",
        "region": "TN",
        "reliability_score": 0.75,
    },
    "kapitalis": {
        "url": "https://www.kapitalis.com/feed",
        "name": "Kapitalis",
        "base_url": "https://www.kapitalis.com",
        "category": "Market",
        "region": "TN",
        "reliability_score": 0.70,
    },
    # ERP & Insurance Technology feeds
    "insurancejournal": {
        "url": "https://www.insurancejournal.com/rss/",
        "name": "Insurance Journal",
        "base_url": "https://www.insurancejournal.com",
        "category": "Insurance",
        "region": "Global",
        "reliability_score": 0.88,
    },
    "insurancebusinessmag": {
        "url": "https://www.insurancebusinessmag.com/rss/",
        "name": "Insurance Business Magazine",
        "base_url": "https://www.insurancebusinessmag.com",
        "category": "Insurance",
        "region": "Global",
        "reliability_score": 0.85,
    },
    "digin": {
        "url": "https://www.dig-in.com/rss/",
        "name": "Digital Insurance",
        "base_url": "https://www.dig-in.com",
        "category": "Insurance",
        "region": "Global",
        "reliability_score": 0.82,
    },
    # Automotive Fleet & Leasing
    "automotivefleet": {
        "url": "https://www.automotivefleet.com/rss/",
        "name": "Automotive Fleet",
        "base_url": "https://www.automotivefleet.com",
        "category": "Fleet",
        "region": "Global",
        "reliability_score": 0.83,
    },
    "fleetmanagement": {
        "url": "https://www.fleet-management.co.uk/rss/",
        "name": "Fleet Management UK",
        "base_url": "https://www.fleet-management.co.uk",
        "category": "Fleet",
        "region": "Europe",
        "reliability_score": 0.80,
    },
}

# XML namespaces used by various feed formats
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "media": "http://search.yahoo.com/mrss/",
}

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

def _fetch_feed_xml(url: str, timeout: int = 20) -> Optional[bytes]:
    """Fetch RSS/Atom XML from url. Returns raw bytes or None on failure."""
    req = Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/rss+xml,application/xml,text/xml,*/*"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = resp.status
            content = resp.read()
            logger.info("Fetched %s — HTTP %s, %d bytes", url, status, len(content))
            return content
    except HTTPError as e:
        logger.warning("HTTP %s fetching %s", e.code, url)
    except URLError as e:
        logger.warning("URLError fetching %s: %s", url, e.reason)
    except Exception as e:
        logger.warning("Failed fetching %s: %s", url, e)
    return None


# ---------------------------------------------------------------------------
# RSS/Atom parser
# ---------------------------------------------------------------------------

def _text(element: Optional[ET.Element]) -> Optional[str]:
    if element is None:
        return None
    return (element.text or "").strip() or None


def _parse_rss_items(xml_bytes: bytes, feed_meta: Dict) -> List[Dict]:
    """Parse RSS 2.0 or Atom feed bytes into a list of article dicts."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        logger.warning("XML parse error: %s", e)
        return []

    items = []
    tag = root.tag.lower()

    # Atom feed
    if "feed" in tag:
        entries = root.findall("atom:entry", _NS) or root.findall("{http://www.w3.org/2005/Atom}entry") or root.findall("entry")
        for entry in entries:
            link_el = entry.find("atom:link", _NS) or entry.find("{http://www.w3.org/2005/Atom}link") or entry.find("link")
            link = None
            if link_el is not None:
                link = link_el.get("href") or _text(link_el)
            title_el = entry.find("atom:title", _NS) or entry.find("{http://www.w3.org/2005/Atom}title") or entry.find("title")
            title = _text(title_el)
            summary_el = entry.find("atom:summary", _NS) or entry.find("atom:content", _NS) or entry.find("{http://www.w3.org/2005/Atom}summary") or entry.find("summary")
            body = _text(summary_el)
            published_el = entry.find("atom:published", _NS) or entry.find("{http://www.w3.org/2005/Atom}published") or entry.find("published")
            pub_date = _parse_date(_text(published_el))
            author_el = entry.find(".//atom:name", _NS) or entry.find(".//{http://www.w3.org/2005/Atom}name")
            author = _text(author_el)
            if title and link:
                items.append({"title": title, "link": link, "body": body, "pub_date": pub_date, "author": author})
        return items

    # RSS 2.0 — find channel/item
    channel = root.find("channel")
    if channel is None:
        # Try direct items (some feeds skip the channel wrapper)
        entries = root.findall("item")
    else:
        entries = channel.findall("item")

    for item in entries:
        title = _text(item.find("title"))
        link = _text(item.find("link"))
        # <link> is sometimes just whitespace — try guid as fallback
        if not link:
            guid = _text(item.find("guid"))
            if guid and guid.startswith("http"):
                link = guid
        body = _text(item.find("{http://purl.org/rss/1.0/modules/content/}encoded")) \
            or _text(item.find("description"))
        pub_raw = _text(item.find("pubDate"))
        pub_date = _parse_date(pub_raw)
        author = _text(item.find("{http://purl.org/dc/elements/1.1/}creator")) \
            or _text(item.find("author"))
        if title and link:
            items.append({"title": title, "link": link, "body": body, "pub_date": pub_date, "author": author})

    return items


def _parse_date(raw: Optional[str]):
    """Parse RFC 2822 or ISO 8601 date string to a date object."""
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


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_or_create_source(session, name: str, base_url: str, reliability_score: float):
    from database.models import ReviewSource
    src = session.query(ReviewSource).filter_by(name=name).first()
    if src:
        return src
    src = ReviewSource(name=name, base_url=base_url, reliability_score=reliability_score, is_active=True)
    session.add(src)
    session.flush()
    return src


def _store_raw_page(session, url: str, xml_bytes: bytes, domain: str):
    from database.models import RawPage
    content_hash = hashlib.sha256(xml_bytes).hexdigest()
    existing = session.query(RawPage).filter_by(content_hash=content_hash).first()
    if existing:
        return existing
    page = RawPage(
        source_url=url,
        source_domain=domain,
        http_status_code=200,
        raw_html=xml_bytes.decode("utf-8", errors="replace"),
        content_hash=content_hash,
        scraper_version="rss-ingest-1.0",
        is_parsed=True,  # will be parsed inline
        scraped_at=datetime.now(timezone.utc),
    )
    session.add(page)
    session.flush()
    return page


def _article_exists(session, source_url: str, content_hash: str) -> bool:
    from database.models import MarketTrendArticle
    return session.query(MarketTrendArticle).filter(
        (MarketTrendArticle.source_url == source_url) |
        (MarketTrendArticle.content_hash == content_hash)
    ).first() is not None


def _store_article(session, item: Dict, source, feed_meta: Dict) -> bool:
    """Insert one article row. Returns True if inserted, False if duplicate/skipped."""
    from database.models import MarketTrendArticle

    url = item["link"]
    title = item["title"][:500] if item["title"] else "Untitled"
    body = item.get("body") or ""

    # Require a minimum body length to avoid stub entries
    if len(body.strip()) < 30:
        body = title  # use title as minimal body

    content_hash = hashlib.sha256(f"{url}|{title}".encode()).hexdigest()

    if _article_exists(session, url, content_hash):
        return False

    article = MarketTrendArticle(
        source_id=source.id,
        title=title,
        source_url=url,
        author=item.get("author"),
        publication_date=item.get("pub_date"),
        body_text=body,
        category=feed_meta["category"],
        region=feed_meta["region"],
        content_hash=content_hash,
        is_processed=False,
        data_origin="scraped",
    )
    session.add(article)
    session.flush()
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_rss_ingest(feed_keys: Optional[List[str]] = None, max_per_feed: int = 20) -> Dict:
    """Fetch all configured RSS feeds and ingest articles into the database.

    Returns summary metrics dict.
    """
    from database.connection import get_db_session

    if feed_keys is None:
        feed_keys = list(FEEDS.keys())

    metrics = {
        "feeds_attempted": 0,
        "feeds_succeeded": 0,
        "articles_inserted": 0,
        "articles_skipped_duplicate": 0,
        "articles_skipped_error": 0,
    }

    separator = "=" * 56
    logger.info(separator)
    logger.info("RSS Ingest starting — feeds=%s, max_per_feed=%d", feed_keys, max_per_feed)
    logger.info(separator)

    for key in feed_keys:
        if key not in FEEDS:
            logger.warning("Unknown feed key '%s' — skipping", key)
            continue

        feed_meta = FEEDS[key]
        feed_url = feed_meta["url"]
        metrics["feeds_attempted"] += 1

        logger.info("── Feed: %s (%s)", feed_meta["name"], feed_url)

        xml_bytes = _fetch_feed_xml(feed_url)
        if xml_bytes is None:
            logger.warning("   FAILED to fetch %s — skipping", key)
            continue

        items = _parse_rss_items(xml_bytes, feed_meta)
        if not items:
            logger.warning("   No items parsed from %s", key)
            continue

        logger.info("   Parsed %d items from feed", len(items))
        items = items[:max_per_feed]

        domain = urlparse(feed_meta["base_url"]).netloc or feed_meta["base_url"]

        inserted = 0
        skipped = 0
        errors = 0

        try:
            with get_db_session() as session:
                # Store raw feed XML in raw_pages for audit trail
                _store_raw_page(session, feed_url, xml_bytes, domain)

                source = _get_or_create_source(
                    session,
                    feed_meta["name"],
                    feed_meta["base_url"],
                    feed_meta["reliability_score"],
                )

                for item in items:
                    try:
                        if _store_article(session, item, source, feed_meta):
                            inserted += 1
                        else:
                            skipped += 1
                    except Exception as e:
                        errors += 1
                        logger.warning("   Error storing article '%s': %s", item.get("title", "?")[:60], e)
                        session.rollback()

                session.commit()
        except Exception as e:
            logger.error("   DB session error for feed %s: %s", key, e)
            continue

        metrics["feeds_succeeded"] += 1
        metrics["articles_inserted"] += inserted
        metrics["articles_skipped_duplicate"] += skipped
        metrics["articles_skipped_error"] += errors

        logger.info(
            "   %s: inserted=%d  duplicate=%d  errors=%d",
            feed_meta["name"], inserted, skipped, errors,
        )

        # Polite delay between feeds
        time.sleep(1.5)

    logger.info(separator)
    logger.info("RSS Ingest complete")
    logger.info("  Feeds succeeded   : %d / %d", metrics["feeds_succeeded"], metrics["feeds_attempted"])
    logger.info("  Articles inserted : %d", metrics["articles_inserted"])
    logger.info("  Duplicates skipped: %d", metrics["articles_skipped_duplicate"])
    logger.info(separator)

    return metrics


# ---------------------------------------------------------------------------
# Run NLP on newly ingested articles
# ---------------------------------------------------------------------------

def run_nlp_on_real_articles() -> Dict:
    """Process all scraped articles through NLP pipeline."""
    from database.connection import get_db_session
    from nlp.nlp_pipeline import NlpPipeline
    from observability.step_recorder import StepRecorder, derive_step_status

    logger.info("Running NLP on real articles (data_origin=scraped)…")

    with get_db_session() as session:
        pipeline = NlpPipeline(session=session)
        metrics = pipeline.process_articles(limit=500)
        recorder = StepRecorder(session, "nlp_articles_real", batch_limit=500)
        recorder.start()
        recorder.finish(
            records_processed=metrics["records_processed"],
            records_skipped=metrics["records_skipped"],
            records_failed=metrics["records_failed"],
            records_inserted=metrics["records_processed"],
            error_count=metrics["records_failed"],
            status=derive_step_status(metrics["records_processed"], metrics["records_failed"]),
        )
        session.commit()

    logger.info(
        "NLP complete — processed=%d  failed=%d  skipped=%d",
        metrics["records_processed"], metrics["records_failed"], metrics["records_skipped"],
    )
    return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest real automotive news articles from RSS feeds."
    )
    parser.add_argument(
        "--feeds", nargs="+",
        choices=list(FEEDS.keys()),
        default=None,
        help="Feed keys to ingest (default: all)",
    )
    parser.add_argument(
        "--max-per-feed", type=int, default=20, metavar="N",
        help="Maximum articles to ingest per feed (default: 20)",
    )
    parser.add_argument(
        "--no-nlp", action="store_true",
        help="Skip NLP processing after ingest",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    ingest_metrics = run_rss_ingest(feed_keys=args.feeds, max_per_feed=args.max_per_feed)

    if not args.no_nlp and ingest_metrics["articles_inserted"] > 0:
        run_nlp_on_real_articles()
    elif not args.no_nlp:
        logger.info("No new articles inserted — skipping NLP step.")
