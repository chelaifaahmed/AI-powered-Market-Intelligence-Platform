"""
scrapers/reuters_scraper.py
-----------------------------
Playwright scraper for Reuters automotive & insurance market news.

Collects industry trend articles for market intelligence.
Target data model: MarketTrendArticle
Entity type routed by parser: market_trend_article
"""

from __future__ import annotations

from scrapers.playwright_base_scraper import PlaywrightBaseScraper


class ReutersAutoNewsScraper(PlaywrightBaseScraper):
    """Scrapes automotive and insurance market trend articles from Reuters."""

    source_name = "reuters_auto"
    rate_limit = 0.3

    start_urls = [
        "https://www.reuters.com/business/autos-transportation/",
        "https://www.reuters.com/business/finance/",
        "https://www.reuters.com/technology/",
        # Direct article searches for automotive topics
        "https://www.reuters.com/search/news?blob=electric+vehicle+market",
        "https://www.reuters.com/search/news?blob=car+insurance+premium",
        "https://www.reuters.com/search/news?blob=automotive+market+2025",
    ]

    def _after_navigate(self, page) -> None:
        """Dismiss cookie consent and scroll to load article list."""
        try:
            # Reuters cookie banner
            for selector in [
                "button[data-testid='accept-all-button']",
                "#onetrust-accept-btn-handler",
                "button.btn_primary",
            ]:
                try:
                    page.click(selector, timeout=3000)
                    page.wait_for_timeout(500)
                    break
                except Exception:
                    pass

            # Scroll to reveal more articles
            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                page.wait_for_timeout(800)
        except Exception:
            pass

    def parse(self, html: str) -> list[dict]:
        """Deprecated — parsing handled by ParserPipeline."""
        return []
