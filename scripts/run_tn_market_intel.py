#!/usr/bin/env python3
"""
scripts/run_tn_market_intel.py
-------------------------------
Scrapes Tunisian insurance & automotive market intelligence articles
from institutional, regulatory, and industry sources.

Sources:
  1. Atlas Magazine (search: tunisia)      — English articles on TN insurance market
  2. Middle East Insurance Review (TN tag) — Regional insurance news
  3. FTUSA (ftusanet.org)                  — Tunisian Insurance Federation
  4. CGA (cga.gov.tn)                      — General Insurance Committee
  5. Tunis Re (tunisre.com.tn)             — National reinsurer market trends

Pipeline:
  1. Playwright fetches rendered pages (JS-heavy institutional sites)
  2. BeautifulSoup extracts article cards (title, link, summary, date)
  3. Keyword relevance filter: only stores articles matching TN market keywords
  4. Articles stored in market_trend_articles with region='TN', data_origin='scraped'
  5. PipelineStepRun recorded

Usage:
    python scripts/run_tn_market_intel.py
    python scripts/run_tn_market_intel.py --max-per-source 20
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("scripts.tn_market_intel")

# ---------------------------------------------------------------------------
# TN Sources
# ---------------------------------------------------------------------------
TN_SOURCES = {
    "atlas_mag": {
        "name": "Atlas Magazine",
        "url": "https://www.atlas-mag.net/en/?s=tunisia+insurance",
        "base_url": "https://www.atlas-mag.net",
        "category": "Insurance",
        "parser": "_parse_atlas_mag",
        "reliability_score": 0.85,
    },
    "atlas_mag_auto": {
        "name": "Atlas Magazine Auto",
        "url": "https://www.atlas-mag.net/en/?s=tunisia+automobile",
        "base_url": "https://www.atlas-mag.net",
        "category": "Market",
        "parser": "_parse_atlas_mag",
        "reliability_score": 0.85,
    },
    "meir": {
        "name": "Middle East Insurance Review",
        "url": "https://meinsurancereview.com/News/TagSearch/TagId/684",
        "base_url": "https://meinsurancereview.com",
        "category": "Insurance",
        "parser": "_parse_meir",
        "reliability_score": 0.88,
    },
    "ftusa": {
        "name": "FTUSA",
        "url": "https://www.ftusanet.org/",
        "base_url": "https://www.ftusanet.org",
        "category": "Insurance",
        "parser": "_parse_ftusa",
        "reliability_score": 0.80,
    },
    "cga": {
        "name": "CGA Tunisia",
        "url": "http://www.cga.gov.tn/",
        "base_url": "http://www.cga.gov.tn",
        "category": "Regulation",
        "parser": "_parse_cga",
        "reliability_score": 0.82,
    },
    "tunis_re": {
        "name": "Tunis Re",
        "url": "https://www.tunisre.com.tn/",
        "base_url": "https://www.tunisre.com.tn",
        "category": "Insurance",
        "parser": "_parse_tunis_re",
        "reliability_score": 0.80,
    },
}

# Keyword relevance filter — article must match at least one
TN_KEYWORDS = [
    # Insurance/ERP (English)
    r"insurance", r"insurtech", r"reinsurance",
    r"claims?\s+process", r"e-constat", r"digital\s+transformation",
    r"ERP", r"software", r"automation", r"legacy\s+system",
    # Insurance/ERP (French)
    r"assurance", r"r[ée]assurance", r"sinistre", r"indemnisation",
    r"transformation\s+num[ée]rique", r"num[ée]risation",
    r"gestion\s+des\s+risques", r"tarification",
    # Market dynamics
    r"bancassurance", r"nat\s*cat", r"natural\s+catastrophe",
    r"premium", r"primes?", r"paid\s+claims", r"loss\s+ratio",
    r"solvency", r"solvabilit[ée]", r"chiffre\s+d.affaire",
    r"indicateur", r"r[ée]sultat", r"capital", r"rapport",
    r"newsletter", r"bilan", r"croissance",
    # Tunisian entities
    r"STAR\s+Assurances?", r"COMAR", r"Maghrebia", r"BIAT",
    r"Zitouna\s+Takaful", r"GAT\s+Assurances?", r"ASTREE",
    r"Tunis\s*Re", r"FTUSA", r"CGA",
    r"AMI\s+Assurance", r"CARTE\s+Assurance", r"Lloyd\s+Tunisien",
    # Automotive
    r"automobile", r"automotive", r"motor\s+insurance",
    r"v[ée]hicule", r"Hyundai", r"Toyota",
    # General TN market
    r"Tunisia", r"Tunisi[ae]n", r"Tunisie",
    r"Afrique\s+du\s+Nord", r"Carthage",
    # Catastrophe / regulation
    r"catastrophe", r"r[ée]glementation", r"circulaire",
    r"loi\s+de\s+finance", r"code\s+des\s+assurance",
]
_KEYWORD_RE = re.compile("|".join(TN_KEYWORDS), re.IGNORECASE)


def _is_relevant(title: str, body: str) -> bool:
    """Check if article text matches TN market keywords."""
    text = f"{title} {body}"
    return bool(_KEYWORD_RE.search(text))


def _content_hash(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}|{title}".encode("utf-8", errors="replace")).hexdigest()


# ---------------------------------------------------------------------------
# Parsers — one per source type
# ---------------------------------------------------------------------------

def _parse_atlas_mag(html: str, base_url: str) -> List[Dict]:
    """Parse Atlas Magazine search results — uses h3 > a pattern."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    articles = []

    # Atlas uses h3 tags with links for article titles (no <article> wrapper)
    for heading in soup.find_all(["h2", "h3", "h4"]):
        a = heading.find("a")
        if not a:
            continue
        title = heading.get_text(strip=True)
        link = a.get("href", "")
        if not link or link == "#":
            continue
        if not link.startswith("http"):
            link = urljoin(base_url, link)

        # Skip navigation/menu links
        if any(skip in link.lower() for skip in ["/category/", "/tag/", "/page/", "/author/"]):
            continue

        # Try to get sibling paragraph as summary
        summary = ""
        parent = heading.parent
        if parent:
            p = parent.find("p")
            if p:
                summary = p.get_text(strip=True)
            excerpt = parent.find(class_=re.compile(r"excerpt|summary|desc", re.I))
            if excerpt:
                summary = excerpt.get_text(strip=True)

        date_el = None
        if parent:
            date_el = parent.find("time")
        pub_date = None
        if date_el and date_el.get("datetime"):
            try:
                pub_date = datetime.fromisoformat(
                    date_el["datetime"].replace("Z", "+00:00")
                ).date()
            except (ValueError, TypeError):
                pass

        if title and link and len(title) > 10:
            articles.append({
                "title": title,
                "link": link,
                "body": summary or title,
                "pub_date": pub_date,
                "author": None,
            })

    return articles


def _parse_meir(html: str, base_url: str) -> List[Dict]:
    """Parse Middle East Insurance Review tag page."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    articles = []

    # MEIR uses news cards / list items
    for card in soup.find_all(["article", "div"], class_=re.compile(r"news|article|item", re.I)):
        title_el = card.find(["h2", "h3", "h4", "a"])
        if not title_el:
            continue

        if title_el.name == "a":
            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
        else:
            a = title_el.find("a")
            if a:
                title = a.get_text(strip=True)
                link = a.get("href", "")
            else:
                title = title_el.get_text(strip=True)
                link = ""

        if not link:
            continue
        if not link.startswith("http"):
            link = urljoin(base_url, link)

        summary = ""
        for p in card.find_all("p"):
            txt = p.get_text(strip=True)
            if len(txt) > len(summary):
                summary = txt

        date_el = card.find("time") or card.find(class_=re.compile(r"date", re.I))
        pub_date = None
        if date_el:
            date_text = date_el.get("datetime") or date_el.get_text(strip=True)
            try:
                pub_date = datetime.fromisoformat(
                    date_text.replace("Z", "+00:00")
                ).date()
            except (ValueError, TypeError):
                # Try common formats
                for fmt in ["%d %B %Y", "%B %d, %Y", "%d/%m/%Y", "%Y-%m-%d"]:
                    try:
                        pub_date = datetime.strptime(date_text, fmt).date()
                        break
                    except ValueError:
                        continue

        if title and link and len(title) > 10:
            articles.append({
                "title": title,
                "link": link,
                "body": summary,
                "pub_date": pub_date,
                "author": None,
            })

    return articles


def _parse_ftusa(html: str, base_url: str) -> List[Dict]:
    """Parse FTUSA homepage for news/publications (French institutional site)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    articles = []
    seen_links = set()

    # FTUSA is the Tunisian Insurance Federation — all content is insurance-relevant
    # Extract all meaningful links
    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        text = a_tag.get_text(strip=True)

        if len(text) < 15 or not href:
            continue
        if href.startswith("#") or href.startswith("javascript"):
            continue
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        if href in seen_links:
            continue

        # Include anything that looks like content (not just navigation)
        if any(kw in href.lower() for kw in [
            "actualit", "news", "publi", "rapport", "communiq", "article",
            "pdf", "statisti", "chiffre", "indicat", "e-constat", "sinistre",
            "circulaire", "reglement", "etude", "marche"
        ]):
            seen_links.add(href)
            articles.append({
                "title": text[:500],
                "link": href,
                "body": text,
                "pub_date": None,
                "author": "FTUSA",
            })

    # Headings with links
    for heading in soup.find_all(["h1", "h2", "h3", "h4"]):
        a = heading.find("a")
        if not a:
            continue
        title = heading.get_text(strip=True)
        link = a.get("href", "")
        if not link.startswith("http"):
            link = urljoin(base_url, link)
        if link in seen_links or len(title) < 10:
            continue
        seen_links.add(link)
        articles.append({
            "title": title,
            "link": link,
            "body": title,
            "pub_date": None,
            "author": "FTUSA",
        })

    return articles


def _parse_cga(html: str, base_url: str) -> List[Dict]:
    """Parse CGA gov.tn homepage for regulatory content."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    articles = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        text = a_tag.get_text(strip=True)

        if len(text) < 15 or not href:
            continue
        if href.startswith("#") or href.startswith("javascript"):
            continue
        if not href.startswith("http"):
            href = urljoin(base_url, href)

        if any(kw in href.lower() for kw in ["reglement", "circulai", "communiq", "loi", "decret",
                                               "rapport", "publi", "actuali", "news", "article"]):
            articles.append({
                "title": text[:500],
                "link": href,
                "body": text,
                "pub_date": None,
                "author": "CGA Tunisia",
            })

    return articles


def _parse_tunis_re(html: str, base_url: str) -> List[Dict]:
    """Parse Tunis Re homepage for market trend content (French site)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    articles = []
    seen_links = set()

    # Tunis Re uses div.item with h4 > a for news cards + div.actualites section
    for card in soup.find_all(["article", "div", "section"],
                               class_=re.compile(r"news|actu|article|post|item", re.I)):
        title_el = card.find(["h2", "h3", "h4"])
        if not title_el:
            continue
        a = title_el.find("a") or card.find("a")
        title = title_el.get_text(strip=True)
        link = ""
        if a:
            link = a.get("href", "")
            if not link.startswith("http"):
                link = urljoin(base_url, link)

        summary = ""
        p = card.find("p")
        if p:
            summary = p.get_text(strip=True)

        if title and len(title) > 10 and link and link not in seen_links:
            seen_links.add(link)
            articles.append({
                "title": title,
                "link": link,
                "body": summary or title,
                "pub_date": None,
                "author": "Tunis Re",
            })

    # Also extract all heading+link combos not in cards
    for heading in soup.find_all(["h2", "h3", "h4"]):
        a = heading.find("a")
        if not a:
            continue
        title = heading.get_text(strip=True)
        link = a.get("href", "")
        if not link or link == "#":
            continue
        if not link.startswith("http"):
            link = urljoin(base_url, link)
        if link in seen_links or len(title) < 10:
            continue
        seen_links.add(link)
        articles.append({
            "title": title,
            "link": link,
            "body": title,
            "pub_date": None,
            "author": "Tunis Re",
        })

    # Also extract linked PDFs/reports
    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        text = a_tag.get_text(strip=True)
        if len(text) < 15:
            continue
        if href in seen_links:
            continue
        if any(ext in href.lower() for ext in [".pdf", "rapport", "report", "publication",
                                                "newsletter", "focus", "revue"]):
            if not href.startswith("http"):
                href = urljoin(base_url, href)
            seen_links.add(href)
            articles.append({
                "title": text[:500],
                "link": href,
                "body": text,
                "pub_date": None,
                "author": "Tunis Re",
            })

    return articles


# Parser dispatch
_PARSERS = {
    "_parse_atlas_mag": _parse_atlas_mag,
    "_parse_meir": _parse_meir,
    "_parse_ftusa": _parse_ftusa,
    "_parse_cga": _parse_cga,
    "_parse_tunis_re": _parse_tunis_re,
}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_or_create_source(session, name: str, base_url: str, reliability_score: float):
    from database.models import ReviewSource
    src = session.query(ReviewSource).filter_by(name=name).first()
    if src:
        return src
    src = ReviewSource(
        name=name, base_url=base_url,
        reliability_score=reliability_score,
        is_active=True, region="TN",
    )
    session.add(src)
    session.flush()
    return src


def _article_exists(session, source_url: str, content_hash: str) -> bool:
    from database.models import MarketTrendArticle
    return session.query(MarketTrendArticle).filter(
        (MarketTrendArticle.source_url == source_url) |
        (MarketTrendArticle.content_hash == content_hash)
    ).first() is not None


def _store_article(session, item: Dict, source, category: str) -> bool:
    from database.models import MarketTrendArticle

    url = item["link"]
    title = (item.get("title") or "")[:500]
    body = item.get("body") or title

    if len(title) < 10:
        return False

    ch = _content_hash(url, title)
    if _article_exists(session, url, ch):
        return False

    session.add(MarketTrendArticle(
        source_id=source.id,
        title=title,
        source_url=url,
        author=item.get("author"),
        publication_date=item.get("pub_date"),
        body_text=body,
        category=category,
        region="TN",
        content_hash=ch,
        is_processed=False,
        data_origin="scraped",
    ))
    session.flush()
    return True


def _store_raw_page(session, url: str, html: str, domain: str):
    from database.models import RawPage
    ch = hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()
    session.add(RawPage(
        source_url=url,
        source_domain=domain,
        http_status_code=200,
        raw_html=html,
        content_hash=ch,
        scraper_version="tn-market-intel-1.0",
        is_parsed=True,
        scraped_at=datetime.now(timezone.utc),
    ))


def _record_step_run(session, stats: dict, started: datetime, status: str):
    from database.models import PipelineStepRun
    from database.enums import PipelineStatus
    finished = datetime.now(timezone.utc)
    duration_ms = int((finished - started).total_seconds() * 1000)
    session.add(PipelineStepRun(
        step_name="tn_market_intel_scrape",
        status=PipelineStatus(status),
        started_at=started,
        finished_at=finished,
        duration_ms=duration_ms,
        records_seen=stats["articles_found"],
        records_processed=stats["articles_inserted"],
        records_skipped=stats["articles_duplicate"] + stats["articles_filtered"],
        records_failed=stats["articles_failed"],
        records_inserted=stats["articles_inserted"],
        error_count=stats["articles_failed"],
        step_metadata={
            "sources_scraped": stats["sources_scraped"],
            "articles_filtered": stats["articles_filtered"],
        },
    ))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def ingest_tn_market_intel(max_per_source: int = 25) -> dict:
    """Scrape TN market intelligence articles from institutional sources."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    from database.connection import get_db_session

    run_started = datetime.now(timezone.utc)
    stats = {
        "sources_scraped": 0,
        "pages_fetched": 0,
        "articles_found": 0,
        "articles_inserted": 0,
        "articles_duplicate": 0,
        "articles_filtered": 0,
        "articles_failed": 0,
    }

    logger.info("=" * 60)
    logger.info("TN Market Intelligence Scrape — %d sources, max %d/source",
                len(TN_SOURCES), max_per_source)
    logger.info("=" * 60)

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
        page = context.new_page()

        for key, source_meta in TN_SOURCES.items():
            url = source_meta["url"]
            parser_name = source_meta["parser"]
            parser_fn = _PARSERS[parser_name]
            domain = urlparse(source_meta["base_url"]).netloc

            logger.info("── Source: %s (%s)", source_meta["name"], url)

            try:
                resp = page.goto(url, timeout=25000, wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except PWTimeout:
                    pass

                # Scroll to load dynamic content
                for _ in range(3):
                    page.evaluate("window.scrollBy(0, window.innerHeight)")
                    page.wait_for_timeout(500)

                html = page.content()
                stats["pages_fetched"] += 1

            except PWTimeout:
                logger.warning("Timeout fetching %s — skipping", url)
                stats["articles_failed"] += 1
                continue
            except Exception as exc:
                logger.error("Failed fetching %s: %s", url, exc)
                stats["articles_failed"] += 1
                continue

            # Store raw HTML
            with get_db_session() as session:
                _store_raw_page(session, url, html, domain)

            # Parse articles
            raw_articles = parser_fn(html, source_meta["base_url"])
            logger.info("   Parsed %d raw articles from %s", len(raw_articles), source_meta["name"])
            stats["articles_found"] += len(raw_articles)

            # Deduplicate by URL within this batch
            seen_urls = set()
            unique_articles = []
            for art in raw_articles:
                if art["link"] not in seen_urls:
                    seen_urls.add(art["link"])
                    unique_articles.append(art)
            raw_articles = unique_articles[:max_per_source]

            # Filter by keyword relevance
            relevant = []
            for art in raw_articles:
                if _is_relevant(art.get("title", ""), art.get("body", "")):
                    relevant.append(art)
                else:
                    stats["articles_filtered"] += 1

            logger.info("   After keyword filter: %d relevant articles", len(relevant))

            # Store articles
            inserted = 0
            with get_db_session() as session:
                source = _get_or_create_source(
                    session, source_meta["name"],
                    source_meta["base_url"],
                    source_meta["reliability_score"],
                )

                for art in relevant:
                    try:
                        if _store_article(session, art, source, source_meta["category"]):
                            inserted += 1
                            stats["articles_inserted"] += 1
                        else:
                            stats["articles_duplicate"] += 1
                    except Exception as exc:
                        logger.warning("   Error storing article: %s", exc)
                        session.rollback()
                        stats["articles_failed"] += 1

            stats["sources_scraped"] += 1
            logger.info("   Inserted %d new articles from %s", inserted, source_meta["name"])

            # Polite delay
            time.sleep(2)

        page.close()
        context.close()
        browser.close()

    # Record pipeline step
    run_status = "success" if stats["articles_failed"] == 0 else (
        "partial" if stats["articles_inserted"] > 0 else "failed"
    )
    try:
        with get_db_session() as session:
            _record_step_run(session, stats, run_started, run_status)
        logger.info("Recorded PipelineStepRun (status=%s)", run_status)
    except Exception as exc:
        logger.warning("Could not record step run: %s", exc)

    # Summary
    logger.info("=" * 60)
    logger.info("TN Market Intelligence Scrape — Summary")
    logger.info("=" * 60)
    logger.info("Sources scraped:    %d", stats["sources_scraped"])
    logger.info("Pages fetched:      %d", stats["pages_fetched"])
    logger.info("Articles found:     %d", stats["articles_found"])
    logger.info("Articles inserted:  %d", stats["articles_inserted"])
    logger.info("Articles duplicate: %d", stats["articles_duplicate"])
    logger.info("Articles filtered:  %d (no keyword match)", stats["articles_filtered"])
    logger.info("Articles failed:    %d", stats["articles_failed"])
    logger.info("=" * 60)

    return stats


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Scrape TN market intelligence articles")
    ap.add_argument("--max-per-source", type=int, default=25,
                    help="Max articles per source (default: 25)")
    args = ap.parse_args()
    ingest_tn_market_intel(max_per_source=args.max_per_source)
