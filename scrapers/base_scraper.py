"""
scrapers/base_scraper.py
------------------------
Abstract base class for all automotive scrapers in the platform.

Subclasses must define:
    - source_name  (str)
    - start_urls   (list[str])
    - rate_limit   (float, requests per second)
    - parse(html)  -> list[dict]

The concrete ``fetch_page()`` and ``run()`` methods handle:
    - HTTP fetching via HttpClient
    - Rate limiting
    - Persisting raw HTML to the ``raw_pages`` table
    - Robust error isolation (one page failure does not abort the run)

Logging:
    All scrapers write to the 'scrapers' logger hierarchy.
    Log records are sent to stdout AND logs/scraper.log (RotatingFileHandler).
"""

import hashlib
import logging
import logging.handlers
import os
import sys
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from scrapers.http_client import HttpClient
from scrapers.rate_limiter import RateLimiter

# ---------------------------------------------------------------------------
# Logging setup — executed once when this module is first imported
# ---------------------------------------------------------------------------
_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
)
os.makedirs(_LOG_DIR, exist_ok=True)
_LOG_FILE = os.path.join(_LOG_DIR, "scraper.log")

# Formatter shared by all handlers
_FORMATTER = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# Root 'scrapers' logger
_root_logger = logging.getLogger("scrapers")
if not _root_logger.handlers:
    _root_logger.setLevel(logging.DEBUG)

    # Rotating file handler — 5 MB per file, keep 3 backups
    _fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(_FORMATTER)

    # Stream handler (stdout)
    _sh = logging.StreamHandler(sys.stdout)
    _sh.setLevel(logging.INFO)
    _sh.setFormatter(_FORMATTER)

    _root_logger.addHandler(_fh)
    _root_logger.addHandler(_sh)

logger = logging.getLogger("scrapers.base")

# ---------------------------------------------------------------------------
# Scraper version — bump when the framework changes
# ---------------------------------------------------------------------------
SCRAPER_VERSION = "3A.1.0"


class BaseScraper(ABC):
    """Abstract base class for all Platform scrapers.

    Class-level attributes to override in subclasses:
        source_name (str): Human-readable source identifier, e.g. 'caranddriver'.
        start_urls  (list[str]): Seed URLs to fetch.
        rate_limit  (float): Max requests per second (default: 1.0).

    Abstract methods:
        parse(html: str) -> list[dict]:
            Extract structured data from raw HTML; return a list of record dicts.
    """

    # -----------------------------------------------------------------------
    # Subclass configuration — override these
    # -----------------------------------------------------------------------
    source_name: str = "base"
    start_urls: list[str] = []
    rate_limit: float = 1.0          # requests per second

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def __init__(self) -> None:
        self._limiter = RateLimiter(requests_per_second=self.rate_limit)
        self._client = HttpClient(
            timeout=15,
            max_retries=3,
            rate_limiter=self._limiter,
        )
        self.logger = logging.getLogger(f"scrapers.{self.source_name}")
        self.logger.info(
            "Scraper '%s' initialised — %d URL(s) queued, rate=%.2f req/s",
            self.source_name,
            len(self.start_urls),
            self.rate_limit,
        )

    # -----------------------------------------------------------------------
    # Abstract interface
    # -----------------------------------------------------------------------

    @abstractmethod
    def parse(self, html: str) -> list[dict]:
        """Extract structured records from raw HTML.

        Args:
            html (str): Raw HTML content of the fetched page.

        Returns:
            list[dict]: Parsed records; schema is scraper-specific.
        """

    # -----------------------------------------------------------------------
    # Concrete helpers
    # -----------------------------------------------------------------------

    def fetch_page(self, url: str) -> Optional[str]:
        """Download a page, persist it to ``raw_pages``, and return raw HTML.

        On any error the exception is logged and ``None`` is returned, so the
        caller can continue processing remaining URLs.

        Args:
            url (str): The page URL to fetch.

        Returns:
            str | None: Raw HTML string, or ``None`` on failure.
        """
        self.logger.info("Fetching: %s", url)
        html: Optional[str] = None
        http_status: Optional[int] = None

        try:
            response = self._client.get(url)
            http_status = response.status_code
            html = response.text
            self.logger.info(
                "Fetched %s — status=%d, size=%d chars",
                url, http_status, len(html),
            )
        except Exception as exc:
            self.logger.error("Failed to fetch %s — %s: %s", url, type(exc).__name__, exc)
            # Store failed attempt in DB too (html=None, status from exc if available)
            http_status = getattr(getattr(exc, "response", None), "status_code", None)

        # Always persist to raw_pages (even on failure, for audit trail)
        self._store_raw_page(url=url, html=html, http_status=http_status)
        return html

    def run(self) -> list[dict]:
        """Execute the full scrape: fetch all start_urls, parse results.

        Returns:
            list[dict]: Aggregated parsed results across all URLs.
        """
        self.logger.info(
            "Starting run — source='%s', %d URL(s)",
            self.source_name, len(self.start_urls),
        )
        all_results: list[dict] = []

        for idx, url in enumerate(self.start_urls, start=1):
            self.logger.info("Processing URL %d/%d: %s", idx, len(self.start_urls), url)
            try:
                html = self.fetch_page(url)
                if html:
                    records = self.parse(html)
                    self.logger.info(
                        "Parsed %d record(s) from %s", len(records), url
                    )
                    all_results.extend(records)
                else:
                    self.logger.warning("Skipping parse for %s — no HTML returned", url)
            except Exception as exc:
                # Belt-and-suspenders: fetch_page should not raise, but just in case
                self.logger.error(
                    "Unexpected error processing %s: %s — continuing", url, exc
                )
                continue

        self.logger.info(
            "Run complete — %d total records from %d URL(s)",
            len(all_results), len(self.start_urls),
        )
        self._client.close()
        return all_results

    # -----------------------------------------------------------------------
    # Private — database persistence
    # -----------------------------------------------------------------------

    def _store_raw_page(
        self,
        url: str,
        html: Optional[str],
        http_status: Optional[int],
    ) -> None:
        """Insert one row into ``raw_pages``.

        Uses the synchronous SQLAlchemy session from ``database.connection``.
        On any DB error the exception is logged and swallowed — scraping
        continues.
        """
        try:
            from database.connection import get_db_session
            from database.models import RawPage

            domain = self._extract_domain(url)
            content_hash = (
                hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()
                if html
                else None
            )

            raw_page = RawPage(
                source_url=url,
                source_domain=domain,
                http_status_code=http_status,
                raw_html=html,
                content_hash=content_hash,
                scraper_version=SCRAPER_VERSION,
                is_parsed=False,
                scraped_at=datetime.now(timezone.utc),
            )

            with get_db_session() as session:
                session.add(raw_page)
                # session.commit() is called by the context manager
            self.logger.debug("Stored raw_page for %s (hash=%s…)", url, (content_hash or "")[:16])

        except Exception as db_exc:
            self.logger.error(
                "DB error storing raw_page for %s: %s", url, db_exc
            )

    @staticmethod
    def _extract_domain(url: str) -> str:
        """Return the netloc portion of a URL, e.g. 'www.caranddriver.com'."""
        try:
            return urlparse(url).netloc or url
        except Exception:
            return url
