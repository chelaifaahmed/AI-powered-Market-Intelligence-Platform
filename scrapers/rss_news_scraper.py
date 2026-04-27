"""
scrapers/rss_news_scraper.py
-----------------------------
Generic RSS scraper for news sources that enrich Company Radar.
One module handles all five feeds; each has its own public runner function.

Sources (all verified working 2026-04-07):
  - Motor1           https://www.motor1.com/rss/news/all/         automotive
  - InsideEVs        https://insideevs.com/rss/articles/all/      EV
  - Insurance Journal https://www.insurancejournal.com/feed/      insurance
  - Business News TN  https://www.businessnews.com.tn/feed        TN business
  - L'Economiste     https://www.leconomistemaghrebin.com/feed/   TN/Maghreb economy

Target model: MarketTrendArticle   data_origin='scraped'
"""

from __future__ import annotations

import hashlib
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logger = logging.getLogger("scrapers.rss_news")

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

_DC_NS = "http://purl.org/dc/elements/1.1/"


# ---------------------------------------------------------------------------
# Feed configuration
# ---------------------------------------------------------------------------

@dataclass
class FeedConfig:
    source_name: str
    feed_url: str
    base_url: str
    category: str
    region: Optional[str]
    tags: List[str] = field(default_factory=list)
    reliability: float = 0.85
    encodings: List[str] = field(default_factory=lambda: ["utf-8", "latin-1", "cp1252"])


_FEEDS: List[FeedConfig] = [
    # ── ERP / InsurTech / Digital Transformation feeds (Google News RSS) ──
    FeedConfig(
        source_name="Google News — ERP Insurance",
        feed_url="https://news.google.com/rss/search?q=ERP+insurance+software+management+system&hl=en-US&gl=US&ceid=US:en",
        base_url="https://news.google.com",
        category="ERP",
        region="Global",
        tags=["ERP", "insurance", "management-system", "software"],
        reliability=0.80,
    ),
    FeedConfig(
        source_name="Google News — InsurTech",
        feed_url="https://news.google.com/rss/search?q=insurtech+digital+transformation+insurance+platform+core+system&hl=en-US&gl=US&ceid=US:en",
        base_url="https://news.google.com",
        category="InsurTech",
        region="Global",
        tags=["insurtech", "digital-transformation", "insurance", "platform"],
        reliability=0.80,
    ),
    FeedConfig(
        source_name="Google News — Automotive ERP",
        feed_url="https://news.google.com/rss/search?q=automotive+ERP+dealership+management+fleet+software&hl=en-US&gl=US&ceid=US:en",
        base_url="https://news.google.com",
        category="ERP",
        region="Global",
        tags=["ERP", "automotive", "dealership", "fleet", "management"],
        reliability=0.80,
    ),
    FeedConfig(
        source_name="Google News — Insurance Operations",
        feed_url="https://news.google.com/rss/search?q=insurance+operations+claims+management+core+system+difficulties&hl=en-US&gl=US&ceid=US:en",
        base_url="https://news.google.com",
        category="insurance",
        region="Global",
        tags=["insurance", "operations", "claims", "core-system"],
        reliability=0.80,
    ),
    FeedConfig(
        source_name="Google News — Leasing Software",
        feed_url="https://news.google.com/rss/search?q=leasing+software+digital+transformation+fleet+management+ERP&hl=en-US&gl=US&ceid=US:en",
        base_url="https://news.google.com",
        category="ERP",
        region="Global",
        tags=["leasing", "software", "fleet", "ERP", "digital-transformation"],
        reliability=0.80,
    ),
    # ── Existing feeds ──
    FeedConfig(
        source_name="Motor1",
        feed_url="https://www.motor1.com/rss/news/all/",
        base_url="https://www.motor1.com",
        category="automotive",
        region="Global",
        tags=["motor1", "automotive", "car news"],
        reliability=0.88,
    ),
    FeedConfig(
        source_name="InsideEVs",
        feed_url="https://insideevs.com/rss/articles/all/",
        base_url="https://insideevs.com",
        category="EV",
        region="Global",
        tags=["insideevs", "EV", "electric vehicle"],
        reliability=0.87,
    ),
    FeedConfig(
        source_name="Insurance Journal",
        feed_url="https://www.insurancejournal.com/feed/",
        base_url="https://www.insurancejournal.com",
        category="insurance",
        region="Global",
        tags=["insurance-journal", "insurance", "industry"],
        reliability=0.88,
    ),
    FeedConfig(
        source_name="Business News TN",
        feed_url="https://www.businessnews.com.tn/feed",
        base_url="https://www.businessnews.com.tn",
        category="business",
        region="TN",
        tags=["business-news-tn", "Tunisia", "finance"],
        reliability=0.80,
    ),
    FeedConfig(
        source_name="L'Economiste Maghrebin",
        feed_url="https://www.leconomistemaghrebin.com/feed/",
        base_url="https://www.leconomistemaghrebin.com",
        category="business",
        region="TN",
        tags=["economiste-maghrebin", "Maghreb", "Tunisia", "economy"],
        reliability=0.82,
    ),
]

_FEED_MAP: Dict[str, FeedConfig] = {f.source_name: f for f in _FEEDS}


# ---------------------------------------------------------------------------
# HTTP + parsing helpers
# ---------------------------------------------------------------------------

def _fetch_bytes(url: str, timeout: int = 15) -> Optional[bytes]:
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
        logger.warning("Unexpected error fetching %s: %s", url, e)
    return None


def _decode(raw: bytes, encodings: List[str]) -> str:
    """Try encodings in order; fall back to replace mode."""
    for enc in encodings:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


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


def _clean_text(s: Optional[str]) -> str:
    """Strip HTML entities and excess whitespace."""
    if not s:
        return ""
    import html
    return html.unescape(s).strip()


def _parse_feed(raw: bytes, cfg: FeedConfig) -> List[Dict]:
    """Parse RSS 2.0 or Atom feed; return list of article dicts."""
    text = _decode(raw, cfg.encodings)
    # Remove BOMs and XML declarations that confuse the parser
    text = text.lstrip("\ufeff")
    try:
        root = ET.fromstring(text.encode("utf-8", errors="replace"))
    except ET.ParseError as e:
        logger.warning("[%s] XML parse error: %s", cfg.source_name, e)
        return []

    # RSS 2.0
    channel = root.find("channel")
    items = (channel.findall("item") if channel is not None else []) or root.findall(".//item")

    # Atom fallback
    atom_ns = "http://www.w3.org/2005/Atom"
    if not items:
        items = root.findall(f"{{{atom_ns}}}entry") or root.findall("entry")

    articles = []
    for item in items:
        title = _clean_text(item.findtext("title") or item.findtext(f"{{{atom_ns}}}title"))
        link = (item.findtext("link") or "").strip()
        if not link:
            link_el = item.find(f"{{{atom_ns}}}link")
            if link_el is not None:
                link = link_el.get("href", "").strip()
        if not link:
            guid = item.findtext("guid") or ""
            if guid.startswith("http"):
                link = guid.strip()

        pub_date = _parse_date(
            item.findtext("pubDate") or item.findtext(f"{{{atom_ns}}}updated")
            or item.findtext(f"{{{atom_ns}}}published")
        )
        creator_el = item.find(f"{{{_DC_NS}}}creator")
        author = _clean_text(creator_el.text if creator_el is not None else None)

        # Description for body_text snippet
        desc = _clean_text(item.findtext("description") or item.findtext(f"{{{atom_ns}}}summary") or "")
        # Strip any residual HTML tags
        import re
        desc = re.sub(r"<[^>]+>", "", desc)[:400]

        if title and link:
            articles.append({
                "title": title,
                "link": link,
                "pub_date": pub_date,
                "author": author or None,
                "body_text": desc or title,
            })

    logger.info("[%s] Parsed %d items", cfg.source_name, len(articles))
    return articles


# ---------------------------------------------------------------------------
# Core runner (shared logic)
# ---------------------------------------------------------------------------

def _run_feed(cfg: FeedConfig) -> Dict:
    """Fetch one RSS feed and persist new articles. Returns metrics dict."""
    import os, sys
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    from database.connection import get_db_session
    from database.models import MarketTrendArticle, ReviewSource
    from database.enums import SourceType

    metrics = {"source": cfg.source_name, "fetched": 0, "inserted": 0, "duplicate": 0, "errors": 0}

    raw = _fetch_bytes(cfg.feed_url)
    if not raw:
        metrics["errors"] += 1
        logger.error("[%s] Failed to fetch feed", cfg.source_name)
        return metrics

    articles = _parse_feed(raw, cfg)
    metrics["fetched"] = len(articles)
    if not articles:
        return metrics

    with get_db_session() as session:
        source = session.query(ReviewSource).filter_by(name=cfg.source_name).first()
        if not source:
            source = ReviewSource(
                name=cfg.source_name,
                base_url=cfg.base_url,
                reliability_score=cfg.reliability,
                is_active=True,
                region=cfg.region,
                source_type=SourceType.NEWS_BLOG,
            )
            session.add(source)
            session.flush()
            logger.info("[%s] Created new ReviewSource", cfg.source_name)

        from parsers.data_gateway import clean_article
        for art in articles:
            title = art["title"]
            link = art["link"]
            content_hash = hashlib.sha256(f"{link}|{title}".encode()).hexdigest()

            exists = session.query(MarketTrendArticle).filter(
                (MarketTrendArticle.source_url == link)
                | (MarketTrendArticle.content_hash == content_hash)
            ).first()
            if exists:
                metrics["duplicate"] += 1
                continue

            cleaned = clean_article({
                "title": title,
                "source_url": link,
                "body_text": art.get("body_text", title),
                "author": art.get("author"),
                "publication_date": art["pub_date"],
            })
            if cleaned is None:
                metrics["errors"] += 1
                continue

            record = MarketTrendArticle(
                source_id=source.id,
                title=cleaned["title"],
                source_url=cleaned["source_url"],
                publication_date=cleaned["publication_date"],
                author=cleaned["author"],
                body_text=cleaned["body_text"],
                category=cfg.category,
                region=cfg.region,
                content_hash=content_hash,
                is_processed=False,
                data_origin="scraped",
                tags=cfg.tags,
            )
            session.add(record)
            try:
                session.flush()
                metrics["inserted"] += 1
                logger.info("[%s] Inserted: %s", cfg.source_name, title[:80])
            except Exception as e:
                session.rollback()
                metrics["errors"] += 1
                logger.warning("[%s] Insert failed '%s': %s", cfg.source_name, title[:50], e)

        source.total_records_scraped = (source.total_records_scraped or 0) + metrics["inserted"]
        source.last_scraped_at = datetime.now(timezone.utc)
        session.flush()

    logger.info("[%s] Done: %s", cfg.source_name, metrics)
    return metrics


# ---------------------------------------------------------------------------
# Public runner functions (one per source)
# ---------------------------------------------------------------------------

def run_erp_insurance_scraper() -> Dict:
    return _run_feed(_FEED_MAP["Google News — ERP Insurance"])


def run_insurtech_scraper() -> Dict:
    return _run_feed(_FEED_MAP["Google News — InsurTech"])


def run_automotive_erp_scraper() -> Dict:
    return _run_feed(_FEED_MAP["Google News — Automotive ERP"])


def run_insurance_operations_scraper() -> Dict:
    return _run_feed(_FEED_MAP["Google News — Insurance Operations"])


def run_leasing_software_scraper() -> Dict:
    return _run_feed(_FEED_MAP["Google News — Leasing Software"])


def run_motor1_scraper() -> Dict:
    return _run_feed(_FEED_MAP["Motor1"])


def run_insideevs_scraper() -> Dict:
    return _run_feed(_FEED_MAP["InsideEVs"])


def run_insurance_journal_scraper() -> Dict:
    return _run_feed(_FEED_MAP["Insurance Journal"])


def run_business_news_tn_scraper() -> Dict:
    return _run_feed(_FEED_MAP["Business News TN"])


def run_economiste_maghrebin_scraper() -> Dict:
    return _run_feed(_FEED_MAP["L'Economiste Maghrebin"])


def run_all_rss_scrapers() -> List[Dict]:
    """Run all 5 RSS feeds sequentially. Returns list of per-source metrics."""
    results = []
    for cfg in _FEEDS:
        try:
            results.append(_run_feed(cfg))
        except Exception as e:
            logger.error("[%s] Unhandled error: %s", cfg.source_name, e)
            results.append({"source": cfg.source_name, "fetched": 0, "inserted": 0, "duplicate": 0, "errors": 1})
    return results
