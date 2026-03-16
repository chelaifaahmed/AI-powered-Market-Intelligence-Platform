"""
scrapers/playwright_base_scraper.py
-------------------------------------
Playwright-powered base scraper that replaces the httpx HttpClient with a
real headless Chromium browser.

Why Playwright instead of httpx?
  - Executes JavaScript — most modern sites require it to render content
  - Appears as a real browser — bypasses basic bot-detection headers checks
  - Handles dynamic pagination, lazy-loaded reviews, infinite scroll

Architecture contract (same as BaseScraper):
  - ``run()``  fetches each URL in ``start_urls`` and persists raw HTML
               to ``raw_pages`` (is_parsed=False) via ``_store_raw_page()``.
  - ``parse()`` deprecated abstract stub — not called by run().
  - All subclass scrapers only need to define ``source_name``, ``start_urls``,
    ``rate_limit``, and optionally override ``_after_navigate()`` for
    page-specific interactions (scroll, click "load more", etc.).
"""

from __future__ import annotations

import hashlib
import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger("scrapers.playwright_base")

# Realistic desktop user agents (rotated per session)
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]


class PlaywrightBaseScraper(ABC):
    """Abstract Playwright scraper. Mirrors BaseScraper interface."""

    source_name: str = "playwright_base"
    start_urls: list[str] = []
    rate_limit: float = 0.3       # requests per second (conservative)
    page_load_timeout: int = 30_000   # ms
    wait_after_load: int = 2_000      # ms to wait after networkidle

    def __init__(self) -> None:
        self._run_metrics = {
            "pages_fetched": 0,
            "records_extracted": 0,
            "bytes_downloaded": 0,
        }
        self.logger = logging.getLogger(f"scrapers.{self.source_name}")
        self.logger.info(
            "PlaywrightScraper '%s' initialised — %d URL(s) queued",
            self.source_name, len(self.start_urls),
        )

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def parse(self, html: str) -> list[dict]:
        """Deprecated abstract stub — not called by run()."""

    # ------------------------------------------------------------------
    # Optional hook for subclasses
    # ------------------------------------------------------------------

    def _after_navigate(self, page) -> None:
        """Called after the page loads, before capturing HTML.

        Override to scroll, dismiss cookie banners, click "load more", etc.
        Default: scroll to bottom once to trigger lazy-loading.
        """
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Core run loop
    # ------------------------------------------------------------------

    def run(self, scrape_task_id=None, run_id=None) -> list[dict]:
        """Fetch all start_urls with Playwright and persist HTML to raw_pages."""
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

        self.logger.info(
            "Starting Playwright run — source='%s', %d URL(s)",
            self.source_name, len(self.start_urls),
        )
        self._run_metrics = {"pages_fetched": 0, "records_extracted": 0, "bytes_downloaded": 0}

        user_agent = random.choice(_USER_AGENTS)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1366, "height": 768},
                locale="en-US",
                timezone_id="America/New_York",
                java_script_enabled=True,
            )
            # Hide webdriver fingerprint
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            page = context.new_page()

            for idx, url in enumerate(self.start_urls, start=1):
                self.logger.info("Fetching URL %d/%d: %s", idx, len(self.start_urls), url)
                html: Optional[str] = None
                http_status: Optional[int] = None

                try:
                    response = page.goto(
                        url,
                        timeout=self.page_load_timeout,
                        wait_until="domcontentloaded",
                    )
                    http_status = response.status if response else None

                    # Wait for network to settle
                    try:
                        page.wait_for_load_state("networkidle", timeout=self.wait_after_load)
                    except PWTimeoutError:
                        pass  # networkidle timeout is fine — content is loaded

                    self._after_navigate(page)

                    html = page.content()
                    self._run_metrics["pages_fetched"] += 1
                    self._run_metrics["bytes_downloaded"] += len(html.encode("utf-8", errors="replace"))
                    self.logger.info(
                        "Fetched %s — status=%s, size=%d chars",
                        url, http_status, len(html),
                    )

                except PWTimeoutError:
                    self.logger.warning("Timeout fetching %s", url)
                except Exception as exc:
                    self.logger.error("Failed fetching %s — %s: %s", url, type(exc).__name__, exc)

                self._store_raw_page(url, html, http_status, scrape_task_id, run_id)

                # Polite delay between pages
                if idx < len(self.start_urls):
                    sleep_s = (1.0 / self.rate_limit) + random.uniform(0.5, 2.0)
                    self.logger.debug("Sleeping %.1f s before next URL", sleep_s)
                    time.sleep(sleep_s)

            page.close()
            context.close()
            browser.close()

        self.logger.info(
            "Playwright run complete — %d page(s) fetched, %d bytes",
            self._run_metrics["pages_fetched"],
            self._run_metrics["bytes_downloaded"],
        )
        return []

    def get_run_metrics(self) -> dict:
        return dict(self._run_metrics)

    # ------------------------------------------------------------------
    # DB persistence (identical to BaseScraper._store_raw_page)
    # ------------------------------------------------------------------

    def _store_raw_page(
        self,
        url: str,
        html: Optional[str],
        http_status: Optional[int],
        scrape_task_id=None,
        run_id=None,
    ) -> None:
        try:
            from database.connection import get_db_session
            from database.models import RawPage

            domain = urlparse(url).netloc or url
            content_hash = (
                hashlib.sha256(html.encode("utf-8", errors="replace")).hexdigest()
                if html else None
            )
            with get_db_session() as session:
                session.add(RawPage(
                    scrape_task_id=scrape_task_id,
                    source_url=url,
                    source_domain=domain,
                    http_status_code=http_status,
                    raw_html=html,
                    content_hash=content_hash,
                    scraper_version="playwright-1.0",
                    is_parsed=False,
                    scraped_at=datetime.now(timezone.utc),
                ))
        except Exception as db_exc:
            self.logger.error("DB error storing raw_page for %s: %s", url, db_exc)
